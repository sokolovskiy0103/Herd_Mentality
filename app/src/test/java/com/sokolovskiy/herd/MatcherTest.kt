package com.sokolovskiy.herd

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MatcherTest {

    @Test fun sameMeaningForms() {
        assertTrue(FuzzyMatcher.same("в машині", "Машина!"))
        assertTrue(FuzzyMatcher.same("книжка", "книжку"))
        assertTrue(FuzzyMatcher.same("оргазм", "Оргазм."))
        assertTrue(FuzzyMatcher.same("холодильник", "холодильнік")) // typo
    }

    @Test fun differentThingsStayApart() {
        assertFalse(FuzzyMatcher.same("пиво", "вино"))
        assertFalse(FuzzyMatcher.same("кіт", "кит"))
        assertFalse(FuzzyMatcher.same("3", "4"))
        assertFalse(FuzzyMatcher.same("кухня", "ванна"))
    }

    @Test fun grouping() {
        val g = FuzzyMatcher.group(listOf("книжка", "аптечка", "Книжку", "праска", "книжка"))
        assertEquals(listOf(listOf(0, 2, 4), listOf(1), listOf(3)), g)
    }

    @Test fun parseModelLabels() {
        val out = "Sure!\n```json\n{\"labels\": [\"Машина\", \"машину\", \"пляж\"]}\n```"
        val labels = JudgePrompt.parseLabels(out, 4)!!
        assertEquals(listOf("машина", "машину", "пляж", "#3"), labels)
        // stemmed labels match; the missing 4th label stays alone
        assertEquals(listOf(listOf(0, 1), listOf(2), listOf(3)), JudgePrompt.groupByLabel(labels))
        assertNull(JudgePrompt.parseLabels("no json here", 3))
        assertNull(JudgePrompt.parseLabels("{\"labels\": []}", 3))
    }

    @Test fun missingLabelsNeverMergeWithNumbers() {
        val labels = JudgePrompt.parseLabels("{\"labels\": [\"0\"]}", 2)!!
        assertEquals(2, JudgePrompt.groupByLabel(labels).size)
    }

    @Test fun examplesAreConsistent() {
        for ((u, m) in JudgePrompt.EXAMPLES) {
            val n = u.lines().count { Regex("^\\d+\\. ").containsMatchIn(it) }
            assertEquals(n, JudgePrompt.parseLabels(m, n)!!.size)
            assertFalse(m.contains("#"))
        }
    }

    @Test fun promptListsAnswers() {
        val p = JudgePrompt.user("Q?", listOf("a", "b"))
        assertTrue(p.contains("1. a") && p.contains("2. b") && p.contains("exactly 2 labels") && p.contains("Question: Q?"))
    }
}
