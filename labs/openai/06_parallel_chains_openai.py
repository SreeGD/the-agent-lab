import time

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel

load_dotenv()

model = ChatOpenAI(model="gpt-4o", temperature=0)
parser = StrOutputParser()


def make_chain(template):
    prompt = ChatPromptTemplate.from_messages([("human", template)])
    return prompt | model | parser


eli5_chain = make_chain(
    "Explain {topic} like I'm 5 years old, in 2-3 sentences. Use a simple everyday analogy."
)
senior_chain = make_chain(
    "Explain {topic} to a senior backend engineer in exactly 3 bullet points. Technical, terse, no filler."
)
haiku_chain = make_chain(
    "Write a haiku (5-7-5 syllables) about {topic}. Output ONLY the haiku, no title, no commentary."
)

topic_input = {"topic": "prompt caching"}


# ---- Sequential baseline ----------------------------------------------------

print("=== SEQUENTIAL (one chain after another) ===")
seq_start = time.perf_counter()

t0 = time.perf_counter()
eli5_out = eli5_chain.invoke(topic_input)
eli5_t = time.perf_counter() - t0

t0 = time.perf_counter()
senior_out = senior_chain.invoke(topic_input)
senior_t = time.perf_counter() - t0

t0 = time.perf_counter()
haiku_out = haiku_chain.invoke(topic_input)
haiku_t = time.perf_counter() - t0

seq_total = time.perf_counter() - seq_start

print(f"  eli5:    {eli5_t:5.2f}s")
print(f"  senior:  {senior_t:5.2f}s")
print(f"  haiku:   {haiku_t:5.2f}s")
print(f"  TOTAL wall-clock: {seq_total:.2f}s  (≈ sum of branches)")


# ---- Parallel run -----------------------------------------------------------

# RunnableParallel runs each branch concurrently against the same input dict.
# It returns a single dict keyed by branch name.
parallel = RunnableParallel(
    eli5=eli5_chain,
    senior=senior_chain,
    haiku=haiku_chain,
)
# Equivalent dict-literal shorthand:
#   parallel = {"eli5": eli5_chain, "senior": senior_chain, "haiku": haiku_chain}
# (LCEL auto-wraps a plain dict into a RunnableParallel when piped into the next step.)

print("\n=== PARALLEL (RunnableParallel) ===")
par_start = time.perf_counter()
result = parallel.invoke(topic_input)
par_total = time.perf_counter() - par_start

print(f"  TOTAL wall-clock: {par_total:.2f}s  (≈ max of branches)")
print(f"  Speedup vs sequential: {seq_total / par_total:.2f}x")


# ---- Outputs ----------------------------------------------------------------

print("\n=== Outputs ===")
print("\n--- ELI5 ---")
print(result["eli5"])
print("\n--- SENIOR ENGINEER ---")
print(result["senior"])
print("\n--- HAIKU ---")
print(result["haiku"])
