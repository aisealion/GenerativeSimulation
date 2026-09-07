# Reads: state/runtime.json (this round's raw proposals from propose).
# Writes: state/runtime.json (per-agent critique dialogue + final refined
# proposal).
#
# Runs after propose, before vote — every proposal gets an independent,
# bounded critique-then-revise loop before anyone votes on it. The critique
# agent (engine.llm_agents.call_critique_agent — a fixed, neutral role, not
# a fisher persona) may only identify missing institutional specification;
# it must never prescribe a normative answer itself (see
# CRITIQUE_SYSTEM_PROMPT). The proposing fisher answers in character via
# the existing call_fisher_agent() path (action_name="critique_response")
# and may revise their own policy/operationalization in response — the
# refined text, never the critique agent's own words, is what actually
# changes the proposal. If any exchange happened at all, a final
# action_name="critique_finalize" call asks the proposer for one
# deliberate, complete restatement incorporating the whole discussion —
# added 2026-09-05 so "the refined operationalization" is an explicit,
# labeled step rather than just whatever the last in-the-moment exchange's
# incidental revision happened to produce. vote.py's own _proposals()
# prefers this action's output over propose's raw one whenever both exist
# for the same round.

from engine.llm_agents import call_critique_agent, call_fisher_agent
from engine.action_base import Action
from engine.physics import alive_agent_ids

MAX_CRITIQUE_EXCHANGES = 5


class CritiqueAction(Action):
    name = "critique"

    def run(self, state):
        runtime = state["runtime"]
        agents = state["agents"]
        round_number = state["round_number"]
        agent_ids = alive_agent_ids(agents, runtime)

        last_propose = next(r for r in reversed(runtime["rounds"]) if r["action"] == "propose")

        refined_proposals = {}
        dialogues = {}
        for agent_id in agent_ids:
            proposal = dict(last_propose["proposals"][agent_id])
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
                    # A malformed but non-erroring response (status missing
                    # or unrecognized, no question either) — nothing left to
                    # ask the proposer, stop rather than loop on emptiness.
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
                # At least one exchange happened — ask for one deliberate
                # final statement rather than trusting the last exchange's
                # own incidental restatement (which was itself an answer
                # to one specific question, not necessarily written as a
                # considered final draft).
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

            refined_proposals[agent_id] = proposal
            dialogues[agent_id] = dialogue

        round_record = {
            "round": round_number,
            "action": "critique",
            "proposals": refined_proposals,
            "dialogues": dialogues,
        }

        runtime["round"] = round_number
        runtime["rounds"].append(round_record)
        return round_record

    def memory_writes(self, state, round_record):
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


ACTION = CritiqueAction()
