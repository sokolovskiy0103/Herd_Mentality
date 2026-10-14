package com.sokolovskiy.herd

import android.content.Context
import android.util.Log
import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.server.application.install
import io.ktor.server.cio.CIO
import io.ktor.server.engine.EmbeddedServer
import io.ktor.server.engine.embeddedServer
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.routing.get
import io.ktor.server.routing.routing
import io.ktor.server.websocket.*
import io.ktor.websocket.Frame
import io.ktor.websocket.readText
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import kotlin.time.Duration.Companion.seconds

/**
 * Local HTTP + WebSocket server. The host's WebView and every player's browser load
 * pages from here and keep one WebSocket open; the server pushes full state snapshots.
 */
class GameServer(private val context: Context) {

    val hostToken: String = UUID.randomUUID().toString().replace("-", "")
    var port = 0; private set

    private val lock = Any()
    private val game = Game(
        QuestionBank.fromJson(context.assets.open("web/questions.json").bufferedReader().use { it.readText() })
    )
    val judge = Judge(context) { broadcast() }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var server: EmbeddedServer<*, *>? = null
    @Volatile private var judging = false
    private var judgeRun = 0

    private class Conn(val isHost: Boolean) {
        val outbox = Channel<String>(Channel.CONFLATED)
        @Volatile var playerId: String? = null
    }

    private val conns = ConcurrentHashMap.newKeySet<Conn>()

    fun start() {
        if (server != null) return
        port = NetUtil.freePort(8080)
        judge.init()
        server = embeddedServer(CIO, port = port, host = "0.0.0.0") {
            install(WebSockets) {
                pingPeriod = 10.seconds
                timeout = 30.seconds
            }
            routing {
                get("/") { serveAsset(call, "play.html") }
                get("/host") { serveAsset(call, "host.html") }
                get("/static/{file}") { serveAsset(call, call.parameters["file"] ?: "") }
                get("/qr.svg") {
                    val text = call.request.queryParameters["t"] ?: ""
                    call.respondText(NetUtil.qrSvg(text), ContentType.parse("image/svg+xml"))
                }
                webSocket("/ws") {
                    val isHost = call.request.queryParameters["host"] == hostToken
                    val conn = Conn(isHost)
                    conns += conn
                    val sender = launch {
                        for (msg in conn.outbox) send(Frame.Text(msg))
                    }
                    sendState(conn)
                    try {
                        for (frame in incoming) {
                            if (frame is Frame.Text) handle(conn, frame.readText())
                        }
                    } catch (t: Throwable) {
                        Log.d(TAG, "ws closed: ${t.message}")
                    } finally {
                        conns -= conn
                        sender.cancel()
                        conn.playerId?.let { pid ->
                            synchronized(lock) {
                                if (conns.none { it.playerId == pid }) game.players[pid]?.connected = false
                            }
                        }
                        broadcast()
                    }
                }
            }
        }.also { it.start(wait = false) }
        Log.i(TAG, "Server on port $port")
    }

    fun stop() {
        server?.stop(500, 1000)
        server = null
    }

    private suspend fun serveAsset(call: io.ktor.server.application.ApplicationCall, name: String) {
        if (name.isEmpty() || name.contains("..") || name.contains('/')) {
            call.respondText("Not found", status = HttpStatusCode.NotFound); return
        }
        val bytes = try {
            context.assets.open("web/$name").use { it.readBytes() }
        } catch (_: Exception) {
            call.respondText("Not found", status = HttpStatusCode.NotFound); return
        }
        val type = when (name.substringAfterLast('.')) {
            "html" -> ContentType.Text.Html.withParameter("charset", "utf-8")
            "css" -> ContentType.Text.CSS.withParameter("charset", "utf-8")
            "js" -> ContentType.Application.JavaScript.withParameter("charset", "utf-8")
            "json" -> ContentType.Application.Json
            "svg" -> ContentType.parse("image/svg+xml")
            else -> ContentType.Application.OctetStream
        }
        call.respondBytes(bytes, type)
    }

    // ---------- messages ----------

    private fun handle(conn: Conn, text: String) {
        val m = try { JSONObject(text) } catch (_: Exception) { return }
        val t = m.optString("t")
        var toJudge: List<Pair<String, String>>? = null
        var question = ""
        synchronized(lock) {
            when (t) {
                // --- player (host can play too) ---
                "join" -> {
                    val p = game.join(m.optString("name"), m.optString("pid").ifEmpty { null })
                    p.connected = true
                    conn.playerId = p.id
                    conn.outbox.trySend(JSONObject().put("t", "welcome").put("pid", p.id).toString())
                }
                "resume" -> {
                    val pid = m.optString("pid")
                    val p = game.players[pid]
                    if (p != null) {
                        p.connected = true
                        conn.playerId = pid
                    } else {
                        conn.outbox.trySend(JSONObject().put("t", "unknown").toString())
                    }
                }
                "answer" -> conn.playerId?.let { game.submitAnswer(it, m.optString("text")) }
                "leave" -> conn.playerId?.let { game.remove(it); conn.playerId = null }
            }
            if (conn.isHost) when (t) {
                "levels" -> {
                    val arr = m.optJSONArray("levels") ?: JSONArray()
                    game.setLevels((0 until arr.length()).map { arr.getString(it) })
                }
                "anonymous" -> game.anonymous = m.optBoolean("on", false)
                "target" -> game.target = m.optInt("target", 8).coerceIn(3, 20)
                "start" -> game.start()
                "skip" -> if (game.phase == Game.Phase.QUESTION) game.nextQuestion()
                "custom" -> if (game.phase == Game.Phase.QUESTION || game.phase == Game.Phase.RESULTS) game.customQuestion(m.optString("text"))
                "reveal" -> if (game.phase == Game.Phase.QUESTION) {
                    toJudge = game.closeAnswers()
                    question = game.question
                }
                "regroup" -> if (game.phase == Game.Phase.JUDGING) {
                    toJudge = game.answers.entries.filter { it.key in game.players }.map { it.key to it.value }
                    question = game.question
                }
                "move" -> game.move(m.optString("pid"), m.optInt("to", -1))
                "confirm" -> if (!judging) game.confirm()
                "next" -> if (game.phase == Game.Phase.RESULTS) game.nextQuestion()
                "newGame" -> {
                    judgeRun++          // drop any judging still in flight
                    judging = false
                    game.newGame()
                }
                "kick" -> game.remove(m.optString("pid"))
                "downloadModel" -> judge.download()
                "deleteModel" -> judge.deleteModel()
            }
        }
        toJudge?.let { runJudge(it, question) }
        broadcast()
    }

    private fun runJudge(list: List<Pair<String, String>>, question: String) {
        val run = synchronized(lock) { ++judgeRun }
        judging = true
        broadcast()
        scope.launch {
            val verdict = try {
                judge.group(question, list.map { it.second })
            } catch (t: Throwable) {
                Log.w(TAG, "judge crashed", t)
                Judge.Verdict(FuzzyMatcher.group(list.map { it.second }), "fuzzy", null)
            }
            synchronized(lock) {
                if (run == judgeRun) {
                    game.applyGroups(list, verdict.groups, verdict.source, verdict.labels)
                    judging = false
                }
            }
            broadcast()
        }
    }

    // ---------- state ----------

    fun broadcast() {
        for (c in conns) sendState(c)
    }

    private fun sendState(c: Conn) {
        val json = synchronized(lock) {
            val o = game.stateJson(c.playerId, c.isHost)
            o.put("t", "state")
            o.put("judging", judging)
            if (c.isHost) {
                o.put("ai", judge.statusJson())
                val addrs = NetUtil.lanAddresses()
                o.put("urls", JSONArray(addrs.map {
                    JSONObject().put("url", "http://${it.ip}:$port/").put("hotspot", it.isHotspot)
                }))
            }
            o.toString()
        }
        c.outbox.trySend(json)
    }

    companion object {
        private const val TAG = "HerdServer"
    }
}
