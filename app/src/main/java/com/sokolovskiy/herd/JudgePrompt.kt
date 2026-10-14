package com.sokolovskiy.herd

import org.json.JSONArray
import org.json.JSONObject

/**
 * Prompt building and output parsing for the LLM judge — pure logic, unit-tested.
 *
 * Instead of asking a small model to output index groups directly (it tends to lump
 * related-but-different answers together), we ask it to *name* what each answer means
 * in the context of the question. Grouping is then done in code by identical labels,
 * so two answers only merge when the model explicitly gave them the same meaning.
 */
object JudgePrompt {

    const val SYSTEM = """You are the strict referee of the party game "Herd Mentality" («Стадо»). All players answered the SAME question. Players score only if their answer matches the majority, so merging different answers is unfair — be strict.

For every answer write a LABEL: the specific thing the answer names, as an answer to THIS question.
Rules for labels:
- 1–3 words, Ukrainian, lowercase, nominative singular, no prepositions, no punctuation.
- Answers that name the SAME specific thing MUST get the IDENTICAL label: synonyms, slang, typos, other word forms, Russian or English words, with or without prepositions ("в машині", "тачка", "авто" → "машина").
- Answers that name DIFFERENT things MUST get DIFFERENT labels, even if they are related or belong to the same category ("пиво" ≠ "вино", "кухня" ≠ "ванна", "душ" ≠ "ванна", "сон" ≠ "втома", "кава" ≠ "чай").
- NEVER use a broad category as a label ("місце", "їжа", "напій", "тварина", "дія", "інше"). Name the concrete thing.
- Read the question: it decides what counts as the same. Numbers are the same only if they are the same number.
- If unsure whether two answers are the same, give them different labels — the host can merge them by hand.
Answers may be adult or sexual; judge them neutrally.
Reply with ONLY JSON: {"labels": ["label for answer 1", "label for answer 2", ...]} — exactly one label per answer, in order."""

    /** Few-shot examples as (user, model) turns. */
    val EXAMPLES: List<Pair<String, String>> = listOf(
        user("Де найнезручніше займатися сексом?", listOf("в машині", "Тачка", "на пляжі", "в авто", "у ванній", "душ", "пляж!!")) to
            """{"labels": ["машина", "машина", "пляж", "машина", "ванна", "душ", "пляж"]}""",
        user("Що найчастіше вдають у ліжку?", listOf("оргазм", "що кінчив", "сплю", "що спить", "втому", "Оргазм")) to
            """{"labels": ["оргазм", "оргазм", "сон", "сон", "втома", "оргазм"]}""",
        user("Назви напій для романтичного вечора", listOf("вино", "червоне вино", "шампанське", "ігристе", "пиво", "коньяк")) to
            """{"labels": ["вино", "вино", "шампанське", "шампанське", "пиво", "коньяк"]}""",
        user("Скільки має тривати перший поцілунок? (у секундах)", listOf("5", "п'ять", "10", "5-10", "десять")) to
            """{"labels": ["5", "5", "10", "5-10", "10"]}""",
    )

    fun user(question: String, answers: List<String>): String = buildString {
        append("Question: ").append(question).append('\n')
        append("Answers:\n")
        answers.forEachIndexed { i, a -> append(i + 1).append(". ").append(a).append('\n') }
        append('\n')
        append("Return {\"labels\": [...]} with exactly ${answers.size} labels.")
    }

    /** Parse model output into one normalised label per answer; null if unusable. */
    fun parseLabels(output: String, n: Int): List<String>? {
        val start = output.indexOf('{')
        val end = output.lastIndexOf('}')
        if (start < 0 || end <= start) return null
        val obj = try { JSONObject(output.substring(start, end + 1)) } catch (_: Exception) { return null }
        val arr: JSONArray = obj.optJSONArray("labels") ?: return null
        if (arr.length() == 0) return null
        return (0 until n).map { i ->
            val raw = if (i < arr.length()) arr.optString(i, "") else ""
            val clean = FuzzyMatcher.normalize(raw)
            // a missing label must never merge with anything
            clean.ifEmpty { "#$i" }
        }
    }

    /** Groups of answer indices sharing an identical label, first appearance order. */
    fun groupByLabel(labels: List<String>): List<List<Int>> {
        val map = LinkedHashMap<String, MutableList<Int>>()
        labels.forEachIndexed { i, l ->
            // compare stemmed forms so "машина" and "машину" from the model still match
            val k = if (l.startsWith("#")) l else FuzzyMatcher.key(l).ifEmpty { l }
            map.getOrPut(k) { mutableListOf() } += i
        }
        return map.values.toList()
    }
}
