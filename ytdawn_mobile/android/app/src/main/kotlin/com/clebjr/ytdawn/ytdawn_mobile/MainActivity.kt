package com.clebjr.ytdawn.ytdawn_mobile

import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.yausername.ffmpeg.FFmpeg
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLException
import com.yausername.youtubedl_android.YoutubeDLRequest
import com.yausername.youtubedl_android.YoutubeDLResponse
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.util.UUID
import java.util.regex.Pattern
import kotlin.concurrent.thread

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.clebjr.ytdawn/engine"
    private var methodChannel: MethodChannel? = null
    private var currentProcessId: String? = null
    private var activeThread: Thread? = null
    private var activeNativeProcess: Process? = null
    private var isCancelled = false

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        methodChannel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
        methodChannel?.setMethodCallHandler { call, result ->
            when (call.method) {
                "initEngine" -> {
                    thread {
                        try {
                            // Inicializa YoutubeDL
                            YoutubeDL.getInstance().init(applicationContext)

                            // Inicializa FFmpeg para mesclagem e conversão de áudio/vídeo
                            try {
                                FFmpeg.getInstance().init(applicationContext)
                                postToMain { sendLog("[Sistema] Motor FFmpeg inicializado e pronto para mesclagem.") }
                            } catch (fe: Exception) {
                                Log.e("YTDawn", "Erro ao inicializar FFmpeg", fe)
                                postToMain { sendLog("[Aviso] Inicialização FFmpeg: ${fe.localizedMessage}") }
                            }

                            postToMain {
                                sendLog("[Sistema] Engine YTDawn (yt-dlp + FFmpeg) inicializada com sucesso.")
                                result.success(true)
                            }

                            // Checa e atualiza yt-dlp em segundo plano para a versão mais recente
                            try {
                                postToMain { sendLog("[Atualização] Verificando versão mais recente do yt-dlp...") }
                                val status = YoutubeDL.getInstance().updateYoutubeDL(applicationContext, YoutubeDL.UpdateChannel._STABLE)
                                postToMain { sendLog("[Atualização] yt-dlp atualizado para a versão mais recente: $status") }
                            } catch (ue: Exception) {
                                postToMain { sendLog("[Atualização] yt-dlp pronto (canal estável).") }
                            }
                        } catch (e: Exception) {
                            Log.e("YTDawn", "Erro ao inicializar YoutubeDL", e)
                            postToMain {
                                sendLog("[ERRO] Falha ao inicializar motor: ${e.localizedMessage}")
                                result.error("INIT_FAILED", e.localizedMessage, null)
                            }
                        }
                    }
                }

                "getDownloadDir" -> {
                    val dir = getPublicDownloadDir()
                    result.success(dir.absolutePath)
                }

                "startDownload" -> {
                    val urls = call.argument<List<String>>("urls") ?: emptyList()
                    val format = call.argument<String>("format") ?: "MP4 (Vídeo)"
                    val resolution = call.argument<String>("resolution") ?: "1080p"
                    val compression = call.argument<String>("compression") ?: "None"
                    val cookiesPath = call.argument<String>("cookiesPath")
                    val outputDir = call.argument<String>("outputDir") ?: getPublicDownloadDir().absolutePath

                    startDownloadQueue(urls, format, resolution, compression, cookiesPath, outputDir)
                    result.success(true)
                }

                "startConversion" -> {
                    val inputPath = call.argument<String>("inputPath") ?: ""
                    val format = call.argument<String>("format") ?: "MP4"
                    val compression = call.argument<String>("compression") ?: "None"
                    val outputDir = call.argument<String>("outputDir") ?: getPublicDownloadDir().absolutePath

                    startConversionTask(inputPath, format, compression, outputDir)
                    result.success(true)
                }

                "cancelTask" -> {
                    cancelCurrentTask()
                    result.success(true)
                }

                "updateEngine" -> {
                    thread {
                        postToMain { sendLog("[Atualização] Baixando a versão mais recente do yt-dlp...") }
                        try {
                            val status = YoutubeDL.getInstance().updateYoutubeDL(applicationContext, YoutubeDL.UpdateChannel._STABLE)
                            postToMain { sendLog("[Atualização] Concluído com sucesso: $status") }
                        } catch (e: Exception) {
                            postToMain { sendLog("[Atualização] Erro: ${e.localizedMessage}") }
                        }
                    }
                    result.success(true)
                }

                "clearCache" -> {
                    thread {
                        try {
                            val cacheDir = applicationContext.cacheDir
                            cacheDir.deleteRecursively()
                            postToMain { sendLog("[Cache] Cache do aplicativo limpo com sucesso.") }
                        } catch (e: Exception) {
                            postToMain { sendLog("[Cache] Erro ao limpar cache: ${e.localizedMessage}") }
                        }
                    }
                    result.success(true)
                }

                else -> result.notImplemented()
            }
        }
    }

    private fun postToMain(action: () -> Unit) {
        Handler(Looper.getMainLooper()).post(action)
    }

    private fun sendLog(message: String) {
        methodChannel?.invokeMethod("onLog", message)
    }

    private fun sendProgress(pct: Double, text: String) {
        methodChannel?.invokeMethod("onProgress", mapOf("progress" to pct, "text" to text))
    }

    private fun sendTaskFinished(success: Boolean, message: String) {
        methodChannel?.invokeMethod("onFinished", mapOf("success" to success, "message" to message))
    }

    private fun getPublicDownloadDir(): File {
        val downloadFolder = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
        val ytdawnDir = File(downloadFolder, "YTDawn")
        if (!ytdawnDir.exists()) {
            ytdawnDir.mkdirs()
        }
        return ytdawnDir
    }

    private fun cancelCurrentTask() {
        isCancelled = true
        currentProcessId?.let { pid ->
            thread {
                try {
                    YoutubeDL.getInstance().destroyProcessById(pid)
                } catch (e: Exception) {
                    Log.e("YTDawn", "Erro ao parar processo $pid", e)
                }
            }
        }
        activeNativeProcess?.let { p ->
            try {
                p.destroy()
            } catch (e: Exception) {
                // Ignore
            }
        }
        postToMain {
            sendLog("[CANCELADO] Operação interrompida pelo usuário.")
            sendTaskFinished(false, "Operação cancelada.")
        }
    }

    private fun findFFmpegExecutable(): File? {
        val noBackup = applicationContext.noBackupFilesDir
        val appFiles = applicationContext.filesDir
        val candidates = listOf(
            File(noBackup, "youtubedl-android/packages/ffmpeg/bin/ffmpeg"),
            File(noBackup, "youtubedl-android/packages/ffmpeg/usr/bin/ffmpeg"),
            File(noBackup, "youtubedl-android/packages/ffmpeg/ffmpeg"),
            File(appFiles, "usr/bin/ffmpeg"),
            File(appFiles, "bin/ffmpeg"),
            File(appFiles, "ffmpeg"),
            File(applicationContext.applicationInfo.nativeLibraryDir, "libffmpeg.so")
        )
        for (c in candidates) {
            if (c.exists() && c.canExecute()) return c
        }

        // Busca recursiva em noBackup
        try {
            val foundNoBackup = noBackup.walkTopDown().firstOrNull {
                (it.name == "ffmpeg" || it.name == "libffmpeg.so") && it.canExecute()
            }
            if (foundNoBackup != null) return foundNoBackup
        } catch (_: Exception) {}

        // Busca recursiva em filesDir
        try {
            val foundFiles = appFiles.walkTopDown().firstOrNull {
                (it.name == "ffmpeg" || it.name == "libffmpeg.so") && it.canExecute()
            }
            if (foundFiles != null) return foundFiles
        } catch (_: Exception) {}

        return null
    }

    private fun startDownloadQueue(
        urls: List<String>,
        format: String,
        resolution: String,
        compression: String,
        cookiesPath: String?,
        outputDir: String
    ) {
        isCancelled = false
        val destDir = File(outputDir)
        if (!destDir.exists()) destDir.mkdirs()

        activeThread = thread {
            val total = urls.size
            postToMain {
                sendLog("=== INICIANDO DOWNLOAD (${total} link(s)) ===")
                sendLog("Formato: $format | Resolução: $resolution | Compressão: $compression")
                sendLog("Destino: ${destDir.absolutePath}")
            }

            // Localiza e informa FFmpeg
            val ffmpegBin = findFFmpegExecutable()
            if (ffmpegBin != null) {
                postToMain { sendLog("[FFmpeg] Binário ativo: ${ffmpegBin.absolutePath}") }
            } else {
                postToMain { sendLog("[FFmpeg] Usando motor interno do youtubedl-android.") }
            }

            val isVideo = format.contains("MP4")
            var anySuccess = false

            for ((idx, rawUrl) in urls.withIndex()) {
                if (isCancelled) break
                val url = rawUrl.trim()
                if (url.isEmpty()) continue

                val currentIdx = idx + 1
                postToMain {
                    sendLog("[$currentIdx/$total] Iniciando download de: $url")
                    sendProgress(0.0, "[$currentIdx/$total] Preparando download...")
                }

                val processId = UUID.randomUUID().toString()
                currentProcessId = processId

                try {
                    val request = YoutubeDLRequest(url)
                    request.addOption("-o", "${destDir.absolutePath}/%(title)s.%(ext)s")
                    request.addOption("--embed-metadata")
                    request.addOption("--embed-thumbnail")

                    // Configura localização do FFmpeg para garantir a mesclagem dos arquivos
                    if (ffmpegBin != null) {
                        request.addOption("--ffmpeg-location", ffmpegBin.parentFile.absolutePath)
                    }

                    // Cookies: verifica o caminho passado ou busca cookies.txt existente
                    val cookieFile = if (!cookiesPath.isNullOrEmpty() && File(cookiesPath).exists()) {
                        File(cookiesPath)
                    } else {
                        val pub = File(destDir, "cookies.txt")
                        if (pub.exists() && pub.length() > 50) pub else null
                    }

                    if (cookieFile != null) {
                        postToMain { sendLog("[Cookies] Usando cookies de: ${cookieFile.name}") }
                        request.addOption("--cookies", cookieFile.absolutePath)
                    }

                    if (!isVideo) {
                        // Áudio MP3
                        request.addOption("-x")
                        request.addOption("--audio-format", "mp3")
                        request.addOption("--audio-quality", "0")
                    } else {
                        // Vídeo MP4 com limite de resolução e mesclagem garantida
                        val maxH = if (resolution.contains("1080")) 1080 else 720
                        val filter = "bv*[height<=$maxH][ext=mp4]+ba[ext=m4a] / bv*[height<=$maxH]+ba / b[height<=$maxH][ext=mp4] / b[height<=$maxH] / bv*+ba / b"
                        request.addOption("-f", filter)
                        request.addOption("--merge-output-format", "mp4")

                        // Compressão via FFmpeg post-processor se solicitado
                        if (compression == "Full") {
                            request.addOption("--postprocessor-args", "ffmpeg:-c:v libx264 -crf 23 -preset faster")
                        } else if (compression == "Half") {
                            request.addOption("--postprocessor-args", "ffmpeg:-c:v libx264 -crf 28 -preset faster")
                        }
                    }

                    val response = YoutubeDL.getInstance().execute(request, processId) { progress, etaInSeconds, line ->
                        if (!isCancelled) {
                            postToMain {
                                val logText = line ?: ""
                                if (logText.isNotEmpty() && !logText.contains("[download]")) {
                                    sendLog("[$currentIdx/$total] $logText")
                                }
                                val statusText = if (etaInSeconds > 0) {
                                    "[$currentIdx/$total] ${progress.toInt()}% (ETA: ${etaInSeconds}s)"
                                } else {
                                    "[$currentIdx/$total] ${progress.toInt()}%"
                                }
                                sendProgress(progress.toDouble(), statusText)
                            }
                        }
                    }

                    if (isCancelled) break

                    anySuccess = true
                    postToMain {
                        sendLog("[$currentIdx/$total] [SUCESSO] Download e mesclagem concluídos com sucesso!")
                        sendProgress(100.0, "[$currentIdx/$total] Concluído!")
                    }

                } catch (e: Exception) {
                    if (isCancelled) break
                    val errMsg = e.localizedMessage ?: "Erro desconhecido"
                    Log.e("YTDawn", "Erro no download de $url", e)
                    postToMain {
                        sendLog("[$currentIdx/$total] [ERRO] Falha no download de ($url): $errMsg")
                    }
                }
            }

            currentProcessId = null
            postToMain {
                if (isCancelled) {
                    sendLog("--- OPERAÇÃO INTERROMPIDA ---")
                    sendTaskFinished(false, "Cancelado")
                } else {
                    sendLog("--- FIM DA FILA DE DOWNLOADS ---")
                    sendProgress(100.0, "Concluído")
                    sendTaskFinished(anySuccess, if (anySuccess) "Downloads finalizados com sucesso!" else "Nenhum download concluído.")
                }
            }
        }
    }

    private fun startConversionTask(
        inputPath: String,
        targetFormat: String,
        compression: String,
        outputDir: String
    ) {
        isCancelled = false
        val inputFile = File(inputPath)
        if (!inputFile.exists()) {
            postToMain {
                sendLog("[ERRO] Arquivo de entrada não encontrado: $inputPath")
                sendTaskFinished(false, "Arquivo inexistente")
            }
            return
        }

        val destDir = File(outputDir)
        if (!destDir.exists()) destDir.mkdirs()

        val baseName = inputFile.nameWithoutExtension
        val ext = targetFormat.lowercase().trim()
        val outputFile = File(destDir, "$baseName.$ext")

        activeThread = thread {
            postToMain {
                sendLog("=== INICIANDO CONVERSÃO COM FFMPEG ===")
                sendLog("Arquivo origem: ${inputFile.name} (${inputFile.length() / 1024 / 1024} MB)")
                sendLog("Formato destino: $targetFormat | Compressão: $compression")
                sendLog("Arquivo de saída: ${outputFile.absolutePath}")
                sendProgress(0.0, "Iniciando FFmpeg...")
            }

            val ffmpegBin = findFFmpegExecutable()
            if (ffmpegBin != null) {
                // Executar FFmpeg diretamente
                val cmd = mutableListOf(
                    ffmpegBin.absolutePath,
                    "-y",
                    "-i", inputFile.absolutePath
                )

                if (ext in listOf("mp4", "mkv", "webm", "avi")) {
                    cmd.addAll(listOf("-c:v", "libx264", "-preset", "faster"))
                    when (compression) {
                        "Full" -> cmd.addAll(listOf("-crf", "23", "-b:a", "128k"))
                        "Half" -> cmd.addAll(listOf("-crf", "28", "-b:a", "96k"))
                        else -> cmd.addAll(listOf("-crf", "18"))
                    }
                } else if (ext == "mp3") {
                    cmd.addAll(listOf("-vn", "-c:a", "libmp3lame", "-q:a", "2"))
                } else if (ext == "wav") {
                    cmd.addAll(listOf("-vn", "-c:a", "pcm_s16le"))
                } else if (ext == "gif") {
                    cmd.addAll(listOf("-vf", "fps=10,scale=480:-1:flags=lanczos"))
                }

                cmd.add(outputFile.absolutePath)

                try {
                    val pb = ProcessBuilder(cmd)
                    pb.redirectErrorStream(true)
                    val process = pb.start()
                    activeNativeProcess = process

                    val reader = BufferedReader(InputStreamReader(process.inputStream))
                    var line: String?
                    val timePattern = Pattern.compile("time=([0-9]{2}):([0-9]{2}):([0-9]{2}\\.[0-9]+)")

                    while (reader.readLine().also { line = it } != null) {
                        if (isCancelled) break
                        val l = line ?: continue
                        if (l.contains("fps=") || l.contains("time=") || l.contains("bitrate=")) {
                            val matcher = timePattern.matcher(l)
                            if (matcher.find()) {
                                postToMain {
                                    sendProgress(50.0, "Convertendo: ${matcher.group(0)}")
                                }
                            }
                        } else if (l.contains("Error") || l.contains("error")) {
                            postToMain { sendLog("[FFmpeg] $l") }
                        }
                    }

                    process.waitFor()
                    activeNativeProcess = null

                    if (isCancelled) {
                        if (outputFile.exists()) outputFile.delete()
                        postToMain {
                            sendLog("[CANCELADO] Conversão interrompida.")
                            sendTaskFinished(false, "Cancelado")
                        }
                    } else if (process.exitValue() == 0 && outputFile.exists()) {
                        postToMain {
                            sendLog("[SUCESSO] Conversão finalizada com sucesso!")
                            sendLog("Arquivo salvo em: ${outputFile.absolutePath} (${outputFile.length() / 1024 / 1024} MB)")
                            sendProgress(100.0, "Conversão concluída!")
                            sendTaskFinished(true, "Conversão concluída com sucesso!")
                        }
                    } else {
                        postToMain {
                            sendLog("[ERRO] FFmpeg retornou código de erro: ${process.exitValue()}")
                            sendTaskFinished(false, "Falha na conversão")
                        }
                    }
                } catch (e: Exception) {
                    activeNativeProcess = null
                    Log.e("YTDawn", "Erro na conversão FFmpeg", e)
                    postToMain {
                        sendLog("[ERRO] Falha ao executar FFmpeg: ${e.localizedMessage}")
                        sendTaskFinished(false, "Erro FFmpeg")
                    }
                }
            } else {
                // Fallback: usar yt-dlp para conversão do arquivo
                val processId = UUID.randomUUID().toString()
                currentProcessId = processId
                try {
                    val request = YoutubeDLRequest(inputFile.absolutePath)
                    request.addOption("-o", outputFile.absolutePath)
                    if (ext == "mp3") {
                        request.addOption("-x")
                        request.addOption("--audio-format", "mp3")
                    } else {
                        request.addOption("--recode-video", ext)
                    }

                    YoutubeDL.getInstance().execute(request, processId) { progress, _, line ->
                        postToMain {
                            sendProgress(progress.toDouble(), "Convertendo: ${progress.toInt()}%")
                            if (!line.isNullOrEmpty()) sendLog("[Conversão] $line")
                        }
                    }

                    postToMain {
                        sendLog("[SUCESSO] Arquivo convertido com sucesso!")
                        sendProgress(100.0, "Concluído!")
                        sendTaskFinished(true, "Conversão concluída!")
                    }
                } catch (e: Exception) {
                    Log.e("YTDawn", "Erro fallback conversão", e)
                    postToMain {
                        sendLog("[ERRO] Erro na conversão: ${e.localizedMessage}")
                        sendTaskFinished(false, "Falha na conversão")
                    }
                } finally {
                    currentProcessId = null
                }
            }
        }
    }
}
