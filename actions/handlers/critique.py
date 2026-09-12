# A bounded multi-turn dialogue between a fixed critique role and the
# proposing fisher, never a single-call-per-agent loop, so this doesn't
# use engine.institution.agent_loop.per_agent_decision() (built for
# exactly one call per agent) — it calls
# engine.llm_agents.call_critique_agent()/call_fisher_agent() directly
# (module-level names — kept this way specifically so existing-style
# monkeypatch tests still work) rather than through ctx.agents, which only
# ever calls the fisher agent under this action's own fixed name. Reuses
# agent_loop.default_ineligible_record() for the one part that IS shared
# with every other handler's loop (the ineligible-agent record shape).
# Still calls ctx.rules around the loop, the same as every other handler,
# so a future rule attached to state["config"]["rules"]["critique"] has
# real effect.
#
# Runs after propose, before vote — every proposal gets an independent,
# bounded critique-then-revise loop before anyone votes on it. See
# engine.llm_agents.CRITIQUE_SYSTEM_PROMPT for the hard boundary: the
# critique role may only ask what a proposal leaves unspecified, never
# prescribe an answer.

from engine.institution.agent_loop import default_ineligible_record
from engine.llm_agents import call_critique_agent, call_fisher_agent

MAX_CRITIQUE_EXCHANGES = 10


def run(ctx):
    state = ctx.state
    runtime = state["runtime"]
    round_number = ctx.round_number

    last_propose = next(r for r in reversed(runtime["rounds"]) if r["action"] == "propose")

    refined_proposals = {}
    dialogues = {}
    for agent_id in ctx.participants:
        propose_record = last_propose["proposals"].get(agent_id, {})
        if "policy" not in propose_record:
            # This agent had no real proposal to critique (e.g. marked
            # ineligible during propose) — nothing to refine.
            continue

        if not ctx.rules.is_eligible(ctx, agent_id):
            refined_proposals[agent_id] = default_ineligible_record(ctx, agent_id)
            dialogues[agent_id] = []
            continue

        proposal = dict(propose_record)
        dialogue = []
        for _exchange in range(MAX_CRITIQUE_EXCHANGES):
            critique = call_critique_agent(
                policy=proposal["policy"],
                operationalization=proposal["operationalization"],
                history=dialogue,
                round_number=round_number,
                proposer_id=agent_id,
            )
            if critique.get("status") == "SUFFICIENT":
                break
            question = critique.get("question", "")
            if not question:
                break
            response = call_fisher_agent(
                agent_id, round_number, "critique_response",
                question=question,
                current_policy=proposal["policy"],
                current_operationalization=proposal["operationalization"],
            )
            dialogue.append({
                "question": question,
                "answer": response.get("answer", ""),
                "revised_policy": response.get("revised_policy", proposal["policy"]),
                "revised_operationalization": response.get(
                    "revised_operationalization", proposal["operationalization"]
                ),
            })
            proposal = {
                "policy": dialogue[-1]["revised_policy"],
                "operationalization": dialogue[-1]["revised_operationalization"],
                "reasoning": proposal.get("reasoning", ""),
            }

        if dialogue:
            dialogue_summary = "\n".join(
                f"- Asked: {turn['question']}\n  You answered: {turn['answer']}"
                for turn in dialogue
            )
            finalize = call_fisher_agent(
                agent_id, round_number, "critique_finalize",
                dialogue_summary=dialogue_summary,
                current_policy=proposal["policy"],
                current_operationalization=proposal["operationalization"],
            )
            proposal = {
                "policy": finalize.get("policy", proposal["policy"]),
                "operationalization": finalize.get(
                    "operationalization", proposal["operationalization"]
                ),
                "reasoning": finalize.get("reasoning", proposal.get("reasoning", "")),
            }

        proposal["participated"] = True
        ctx.rules.apply_after_agent(ctx, agent_id, proposal)
        ctx.rules.settle_agent(ctx, agent_id, proposal)
        refined_proposals[agent_id] = proposal
        dialogues[agent_id] = dialogue

    return {"proposals": refined_proposals, "dialogues": dialogues}


def memory_writes(state, round_record):
    return [
        {
            "event_type": "proposal_refined",
            "text": (
                f"after being asked to clarify your proposal, you refined it to: "
                f"{round_record['proposals'][agent_id]['policy']}"
            ),
            "agent_id": agent_id,
            "group_id": agent_id,
        }
        for agent_id, dialogue in round_record["dialogues"].items()
        if dialogue
    ]
