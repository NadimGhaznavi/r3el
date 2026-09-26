# How to Implement "Full Control" Safely

To make this work, you must treat the LLM not as a random searcher, but as a Hypothesis-Driven Researcher. You need to constrain the search space and force it to justify its choices.

## The "Challenger" Protocol (Instead of Pure Replacement)

Do not throw away the "Golden Configuration" entirely. Instead, use a Challenger System:

1. The LLM is presented with the current Golden Configuration and its score.
2. It is also presented with the Top 3 Historical Configurations and their scores.
3. The LLM is asked to generate one complete, new configuration (the "Challenger") that modifies multiple parameters at once.
4. If the Challenger beats the Golden score, it becomes the new Golden. If it fails, the Golden remains, but the LLM learns from the failure in the next prompt.

## Prompt Engineering for Qwen 3.5 4B

You must force the LLM to output a reasoning field. Qwen 3.5 4B is highly capable of this. Your prompt to the LLM should look like this:
```
"You are an expert Reinforcement Learning engineer. Your goal is to maximize the Snake game high score while respecting a strict compute budget (max 3000 epochs).
Current Golden Configuration Score: 145
Historical Top 3: [List configs and scores]
Propose a COMPLETE new configuration. You may change any parameter, but you MUST provide a 'reasoning' string explaining the RL theory behind your joint choices.
Example reasoning: 'I increased hidden_size to 256 and layers to 2 to capture longer-term dependencies. To prevent gradient explosion from this larger network, I lowered learning_rate to 0.0015 and increased max_gradient_norm to 1.5. I also increased epochs to 2000 to ensure the larger model has time to converge.'
Output valid JSON matching the schema."
```

## Introduce "Efficiency" as a Metric

To prevent the LLM from just maxing out epochs, feed it a secondary metric: Score per 1000 Epochs (or Score per Minute).

- Config A: Score 160 in 3000 epochs = 53.3 per 1000 epochs.
- Config B: Score 145 in 1500 epochs = 96.6 per 1000 epochs.

If you tell the LLM, *"Config B is preferred because it is more compute-efficient,"* it will learn to find elegant, fast-converging solutions rather than brute-forcing with high epochs.

## Summary of the Shift

Aspect | Current (Round Robin) | Proposed (Joint Hypothesis)
--- | --- | ---
Search Strategy | Coordinate Descent (1-2 params) | Joint Hypothesis (All params)
LLM Role | Local optimizer | Holistic RL Researcher
Interactions | Misses coupled effects (e.g., LR + Batch) | Explicitly reasons about couplings
Risk | Slow convergence, local optima | Wasted runs if hypothesis is wild
Mitigation | N/A | Require reasoning field, cap epochs, use Challenger protocol