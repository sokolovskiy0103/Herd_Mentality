package com.sokolovskiy.herd

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.util.Log
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.SamplerConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.io.File

/**
 * Owns the on-device Gemma model: download, load, and judging.
 * Every failure degrades to [FuzzyMatcher]; the game never depends on the model.
 */
class Judge(private val context: Context, private val onChange: () -> Unit) {

    enum class State { ABSENT, DOWNLOADING, LOADING, READY, ERROR }

    @Volatile var state = State.ABSENT; private set
    @Volatile var progress = 0.0; private set
    @Volatile var message = ""; private set
    @Volatile var backendName = ""; private set
    @Volatile var lastMillis = 0L; private set

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val llmLock = Mutex()
    private var engine: Engine? = null

    private val dir: File get() = context.getExternalFilesDir(null) ?: context.filesDir
    private val modelFile: File get() = File(dir, MODEL_NAME)
    private val prefs get() = context.getSharedPreferences("judge", Context.MODE_PRIVATE)

    fun init() {
        val dlId = prefs.getLong("download", -1)
        when {
            dlId >= 0 -> trackDownload(dlId)
            modelFile.exists() && modelFile.length() > MIN_SIZE -> load()
            else -> set(State.ABSENT, "Модель не завантажена")
        }
    }

    fun statusJson(): JSONObject = JSONObject().apply {
        put("state", state.name)
        put("progress", progress)
        put("message", message)
        put("backend", backendName)
        put("lastMillis", lastMillis)
        put("sizeMb", 2590)
    }

    // ---------- download ----------

    fun download() {
        if (state == State.DOWNLOADING || state == State.LOADING || state == State.READY) return
        val dm = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        File(dir, PART_NAME).delete()
        val req = DownloadManager.Request(Uri.parse(MODEL_URL))
            .setTitle("Gemma 4 для гри «Стадо»")
            .setDescription("≈2.6 ГБ, один раз")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
            .setDestinationUri(Uri.fromFile(File(dir, PART_NAME)))
            .setAllowedOverMetered(true)
        val id = dm.enqueue(req)
        prefs.edit().putLong("download", id).apply()
        trackDownload(id)
    }

    fun deleteModel() {
        if (state == State.DOWNLOADING) {
            val dm = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            dm.remove(prefs.getLong("download", -1))
            prefs.edit().remove("download").apply()
        }
        scope.launch {
            llmLock.withLock {
                engine?.close(); engine = null
                modelFile.delete(); File(dir, PART_NAME).delete()
                backendName = ""
                set(State.ABSENT, "Модель видалена")
            }
        }
    }

    private fun trackDownload(id: Long) {
        set(State.DOWNLOADING, "Завантаження…")
        scope.launch {
            val dm = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            while (true) {
                val c = dm.query(DownloadManager.Query().setFilterById(id))
                if (c == null || !c.moveToFirst()) {
                    c?.close()
                    prefs.edit().remove("download").apply()
                    set(State.ERROR, "Завантаження зникло, спробуй ще раз")
                    return@launch
                }
                val status = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                val done = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
                val total = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
                val reason = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON))
                c.close()
                when (status) {
                    DownloadManager.STATUS_SUCCESSFUL -> {
                        prefs.edit().remove("download").apply()
                        val part = File(dir, PART_NAME)
                        if (part.length() > MIN_SIZE && part.renameTo(modelFile)) {
                            load()
                        } else {
                            set(State.ERROR, "Файл моделі пошкоджений (${part.length() / 1_000_000} МБ)")
                        }
                        return@launch
                    }
                    DownloadManager.STATUS_FAILED -> {
                        prefs.edit().remove("download").apply()
                        dm.remove(id)
                        set(State.ERROR, "Завантаження не вдалося (код $reason)")
                        return@launch
                    }
                    else -> {
                        val p = if (total > 0) done.toDouble() / total else 0.0
                        val msg = when (status) {
                            DownloadManager.STATUS_PAUSED -> "Пауза — чекаю на мережу"
                            DownloadManager.STATUS_PENDING -> "В черзі…"
                            else -> "Завантаження ${done / 1_000_000} / ${if (total > 0) total / 1_000_000 else 2590} МБ"
                        }
                        if (p != progress || msg != message) {
                            progress = p; message = msg; onChange()
                        }
                    }
                }
                delay(1000)
            }
        }
    }

    // ---------- load ----------

    private fun load() {
        set(State.LOADING, "Завантажую модель у пам'ять…")
        scope.launch {
            llmLock.withLock {
                engine?.close(); engine = null
                val attempts = listOf("GPU" to { Backend.GPU() }, "CPU" to { Backend.CPU() })
                var lastError: Throwable? = null
                for ((name, backend) in attempts) {
                    try {
                        val e = Engine(
                            EngineConfig(
                                modelPath = modelFile.absolutePath,
                                backend = backend(),
                                cacheDir = context.cacheDir.path,
                            )
                        )
                        e.initialize()
                        engine = e
                        backendName = name
                        set(State.READY, "Gemma 4 готова ($name)")
                        return@withLock
                    } catch (t: Throwable) {
                        Log.w(TAG, "Backend $name failed", t)
                        lastError = t
                    }
                }
                set(State.ERROR, "Не вдалося запустити модель: ${lastError?.message?.take(120)}")
            }
        }
    }

    // ---------- judging ----------

    class Verdict(val groups: List<List<Int>>, val source: String, val labels: List<String>?)

    /**
     * Groups [answers] to [question]. The model labels each answer's meaning; answers with
     * identical labels form a group. Near-identical spellings from [FuzzyMatcher] are always
     * merged on top, so a typo never splits a group even if the model misses it.
     */
    suspend fun group(question: String, answers: List<String>): Verdict {
        val fuzzy = FuzzyMatcher.group(answers)
        if (answers.size < 2) return Verdict(fuzzy, "fuzzy", null)
        val e = engine
        if (state != State.READY || e == null) return Verdict(fuzzy, "fuzzy", null)

        val started = System.currentTimeMillis()
        val llm = withTimeoutOrNull(LLM_TIMEOUT_MS) {
            scope.async(Dispatchers.IO) {
                llmLock.withLock {
                    try {
                        val conv = e.createConversation(
                            ConversationConfig(
                                systemInstruction = Contents.of(JudgePrompt.SYSTEM),
                                initialMessages = JudgePrompt.EXAMPLES.flatMap { (u, m) ->
                                    listOf(Message.user(u), Message.model(m))
                                },
                                samplerConfig = SamplerConfig(topK = 1, topP = 1.0, temperature = 0.0),
                            )
                        )
                        conv.use { it.sendMessage(JudgePrompt.user(question, answers)).toString() }
                    } catch (t: Throwable) {
                        Log.w(TAG, "LLM judge failed", t)
                        null
                    }
                }
            }.await()
        }
        lastMillis = System.currentTimeMillis() - started
        Log.i(TAG, "LLM raw (${lastMillis}ms): $llm")
        val labels = llm?.let { JudgePrompt.parseLabels(it, answers.size) }
            ?: return Verdict(fuzzy, "fuzzy", null)
        val groups = mergeWith(JudgePrompt.groupByLabel(labels), fuzzy, answers.size)
        return Verdict(groups, "gemma", labels)
    }

    private fun mergeWith(a: List<List<Int>>, b: List<List<Int>>, n: Int): List<List<Int>> {
        val parent = IntArray(n) { it }
        fun find(x: Int): Int = if (parent[x] == x) x else find(parent[x]).also { parent[x] = it }
        for (g in a + b) for (i in 1 until g.size) {
            val r1 = find(g[0]); val r2 = find(g[i]); if (r1 != r2) parent[r2] = r1
        }
        return (0 until n).groupBy { find(it) }.values.toList()
    }

    private fun set(s: State, msg: String) {
        state = s; message = msg
        if (s != State.DOWNLOADING) progress = if (s == State.READY) 1.0 else 0.0
        onChange()
    }

    companion object {
        private const val TAG = "HerdJudge"
        const val MODEL_NAME = "gemma-4-E2B-it.litertlm"
        private const val PART_NAME = "gemma-4-E2B-it.litertlm.part"
        const val MODEL_URL =
            "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm"
        private const val MIN_SIZE = 1_000_000_000L
        private const val LLM_TIMEOUT_MS = 45_000L
    }
}
