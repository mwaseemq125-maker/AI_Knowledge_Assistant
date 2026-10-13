ZERO_SHOT_PROMPT = """
Answer the user's question using only the supplied context.
Do not use outside knowledge. If the context does not answer the question,
say: "The uploaded documents do not provide enough information."

Context:
{context}

Question:
{question}

Answer:
"""

FEW_SHOT_PROMPT = """
Answer questions using only the supplied context. Follow the style of these examples.

Example 1
Context: Machine learning systems learn patterns from data.
Question: What is machine learning?
Answer: Machine learning enables systems to learn patterns from data.

Example 2
Context: Embeddings represent text as numerical vectors.
Question: What are embeddings?
Answer: Embeddings are numerical representations of text.

Example 3
Context: Semantic search compares meaning rather than requiring exact word matches.
Question: What is semantic search?
Answer: Semantic search retrieves information based on semantic meaning.

Now answer the user's question. The examples demonstrate format, not facts about
the current documents. Use only the supplied context and do not invent facts.
If the context is insufficient, state that clearly.

Context:
{context}

Question:
{question}

Answer:
"""

ROLE_BASED_PROMPT = """
You are a careful Technical Document Analyst and AI Knowledge Assistant.
Your job is to answer questions about uploaded documents.

Rules:
1. Use only the supplied context as evidence.
2. Be accurate, concise, clear, and directly relevant.
3. Do not fabricate details or citations.
4. If evidence is missing or insufficient, say so explicitly.
5. Explain technical concepts in accessible language.
6. Mention the source filenames when useful.

Context:
{context}

Question:
{question}

Answer:
"""

PROMPT_TEMPLATES = {
    "Zero-shot": ZERO_SHOT_PROMPT,
    "Few-shot": FEW_SHOT_PROMPT,
    "Role-based": ROLE_BASED_PROMPT,
}

TEST_QUESTIONS = [
    "What is artificial intelligence?",
    "How does machine learning work?",
    "What is the purpose of embeddings?",
    "How does semantic search differ from keyword search?",
    "What are the limitations of the information in these documents?",
]
