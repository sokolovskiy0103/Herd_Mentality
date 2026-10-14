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

    @Test fun parseModelOutput() {
        val out = "Sure!\n```json\n{\"groups\": [[1, 3], [2], [3, 9]]}\n```"
        // 3 is duplicated (kept once), 9 is out of range (dropped), 4 missing (own group)
        assertEquals(listOf(listOf(0, 2), listOf(1), listOf(3)), JudgePrompt.parse(out, 4))
        assertNull(JudgePrompt.parse("no json here", 3))
        assertNull(JudgePrompt.parse("{\"groups\": []}", 3))
    }

    @Test fun promptListsAnswers() {
        val p = JudgePrompt.user("Q?", listOf("a", "b"))
        assertTrue(p.contains("1. a") && p.contains("2. b") && p.contains("1 to 2"))
    }
}
