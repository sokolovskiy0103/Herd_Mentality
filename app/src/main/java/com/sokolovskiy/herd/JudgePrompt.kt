package com.sokolovskiy.herd

import org.json.JSONObject

/** Prompt building and output parsing for the LLM judge — pure logic, unit-tested. */
object JudgePrompt {

    const val SYSTEM = """You are the referee of the party game "Herd Mentality". Players answered the same question and you must group answers that mean THE SAME THING.
Same thing = synonyms, slang for the same thing, different word forms, typos, different spelling, with or without prepositions (e.g. "машина", "в машині", "тачка", "авто" are one group).
Different things stay separate even if related (e.g. "пиво" and "вино" are different; "кухня" and "ванна" are different).
Answers are mostly Ukrainian, sometimes Russian or English, and may be adult/sexual — judge them neutrally.
Reply with ONLY a JSON object, no explanations."""

    fun user(question: String, answers: List<String>): String = buildString {
        append("Question: ").append(question).append('\n')
        append("Answers:\n")
        answers.forEachIndexed { i, a -> append(i + 1).append(". ").append(a).append('\n') }
        append('\n')
        append("""Return {"groups": [[numbers of answers in group 1], [numbers in group 2], ...]} using every number from 1 to ${answers.size} exactly once.""")
    }

    /** Parse model output into 0-based index groups; null if unusable. */
    fun parse(output: String, n: Int): List<List<Int>>? {
        val start = output.indexOf('{')
        val end = output.lastIndexOf('}')
        if (start < 0 || end <= start) return null
        val obj = try { JSONObject(output.substring(start, end + 1)) } catch (_: Exception) { return null }
        val arr = obj.optJSONArray("groups") ?: return null
        val seen = HashSet<Int>()
        val groups = mutableListOf<List<Int>>()
        for (i in 0 until arr.length()) {
            val g = arr.optJSONArray(i) ?: continue
            val members = mutableListOf<Int>()
            for (j in 0 until g.length()) {
                val idx = g.optInt(j, -1) - 1
                if (idx in 0 until n && seen.add(idx)) members += idx
            }
            if (members.isNotEmpty()) groups += members
        }
        if (seen.isEmpty()) return null
        // anything the model forgot becomes its own group
        (0 until n).filter { it !in seen }.forEach { groups += listOf(it) }
        return groups
    }
}
