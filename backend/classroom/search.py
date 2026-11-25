"""Ask questions about your courses. Answers come only from course content, with sources.

BM25 over assignments, announcements and materials, rebuilt from the database on
demand (a classroom has hundreds of documents, not millions). An LLM, if
configured, only rephrases the retrieved passages and must cite them; without one,
the best passages are returned directly. If nothing relevant is found the
assistant says so instead of guessing.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import Assignment, Post

log = logging.getLogger(__name__)
_TOK = re.compile(r"[a-z0-9]+")
_STOP = set("a an the of to in on for and or is are be by with as at from that this it its what when where which who how do does did i my me we our you your can will".split())
MIN_SCORE = 2.0  # below this the best match is too weak to answer from


def tokens(text: str) -> list[str]:
    out = []
    for t in _TOK.findall(text.lower()):
        if t in _STOP or len(t) < 2:
            continue
        out.append(t[:-1] if len(t) > 4 and t.endswith("s") else t)  # crude plural folding
    return out


@dataclass
class Doc:
    id: str
    course: str
    kind: str
    title: str
    text: str
    due: str | None = None


def build_corpus(db: Session, course_ids: list[str]) -> list[Doc]:
    docs = []
    for a in db.scalars(select(Assignment).where(Assignment.course_id.in_(course_ids))):
        due = a.due_at.strftime("%d %b %Y, %H:%M UTC") if a.due_at else None
        body = f"{a.description or ''} Due: {due or 'no due date'}. Points: {a.max_points or 'ungraded'}."
        docs.append(Doc(a.id, a.course.name, "assignment", a.title, body, due))
    for p in db.scalars(select(Post).where(Post.course_id.in_(course_ids))):
        docs.append(Doc(p.id, p.course.name, p.kind, p.title or p.kind.title(), p.text))
    return docs


def rank(question: str, docs: list[Doc], k: int = 4) -> list[tuple[Doc, float]]:
    q = tokens(question)
    if not q or not docs:
        return []
    tfs = [Counter(tokens(f"{d.title} {d.title} {d.text}")) for d in docs]  # title counts double
    lens = [sum(tf.values()) for tf in tfs]
    avg = sum(lens) / len(lens)
    df = Counter(t for tf in tfs for t in tf)
    n = len(docs)
    scored = []
    for d, tf, dl in zip(docs, tfs, lens):
        s = 0.0
        for t in q:
            if tf[t]:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * dl / avg))
        if s > 0:
            scored.append((d, s))
    scored.sort(key=lambda x: -x[1])
    return scored[:k]


SYSTEM = """You answer a student's or teacher's question using ONLY the numbered course sources.
Cite sources like [1]. If the sources don't answer it, reply exactly: "I couldn't find that in your course material."
Be brief (under 90 words) and keep dates and numbers exactly as written."""


def answer(db: Session, question: str, course_ids: list[str]) -> dict:
    hits = rank(question, build_corpus(db, course_ids))
    if not hits or hits[0][1] < MIN_SCORE:
        return {"answer": "I couldn't find that in your course material. Try different words, or ask your teacher.",
                "sources": [], "mode": "none"}
    top = hits[0][1]
    hits = [h for h in hits if h[1] >= top * 0.35]  # drop weak tail matches
    sources = [{"n": i + 1, "id": d.id, "course": d.course, "kind": d.kind, "title": d.title,
                "text": d.text, "relevance": round(s / top, 2)} for i, (d, s) in enumerate(hits)]

    s = get_settings()
    if s.llm_enabled:
        try:
            from groq import Groq
            body = "\n".join(f"[{x['n']}] ({x['course']} · {x['kind']}: {x['title']}) {x['text']}" for x in sources)
            r = Groq(api_key=s.groq_api_key).chat.completions.create(
                model=s.groq_model, temperature=0.1, max_tokens=300,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"{body}\n\nQuestion: {question}"}])
            text = r.choices[0].message.content.strip()
            return {"answer": text, "sources": sources, "mode": "llm"}
        except Exception as exc:
            log.warning("LLM failed, falling back to extractive answer: %s", exc)

    best = sources[0]
    return {"answer": f"From {best['course']} · {best['title']}: {best['text']}", "sources": sources, "mode": "extractive"}
