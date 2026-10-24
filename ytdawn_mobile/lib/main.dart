import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:path_provider/path_provider.dart';
import 'package:file_picker/file_picker.dart';
import 'package:share_plus/share_plus.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const YTDawnApp());
}

class YTDawnApp extends StatelessWidget {
  const YTDawnApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'YTDawn Mobile',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF120E24),
        primaryColor: const Color(0xFFEA3A8E),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFEA3A8E),
          secondary: Color(0xFF26D0CE),
          tertiary: Color(0xFFFF8C42),
          surface: Color(0xFF181332),
        ),
        fontFamily: 'Roboto',
      ),
      home: const YTDawnHomePage(),
    );
  }
}

class YTDawnHomePage extends StatefulWidget {
  const YTDawnHomePage({super.key});

  @override
  State<YTDawnHomePage> createState() => _YTDawnHomePageState();
}

class _YTDawnHomePageState extends State<YTDawnHomePage> {
  static const platform = MethodChannel('com.clebjr.ytdawn/engine');

  final TextEditingController _urlsController = TextEditingController();
  final ScrollController _mainScrollController = ScrollController();
  final ScrollController _logScrollController = ScrollController();

  int _activeTabIndex = 0; // 0 = Download, 1 = Conversão

  // Opções de Download
  String _dlFormat = 'MP4 (Vídeo)';
  String _dlResolution = '1080p';
  String _dlCompression = 'None';

  // Opções de Conversão
  String _convFormat = 'MP4';
  String _convCompression = 'None';
  String? _selectedConvertFilePath;
  int? _selectedConvertFileSize;

  // Estado da Aplicação
  bool _isBusy = false;
  String _currentTaskMode = 'none'; // 'download' ou 'convert'
  double _progressPct = 0.0;
  String _statusMessage = 'Pronto para download ou conversão';
  final List<String> _logs = [];

  // Cookies & Storage
  String? _cookiesFilePath;
  bool _hasActiveCookies = false;
  String _downloadDirectory = '/storage/emulated/0/Download/YTDawn';

  @override
  void initState() {
    super.initState();
    _setupMethodChannel();
    _initAppEnvironment();
  }

  @override
  void dispose() {
    _urlsController.dispose();
    _mainScrollController.dispose();
    _logScrollController.dispose();
    super.dispose();
  }

  void _setupMethodChannel() {
    platform.setMethodCallHandler((call) async {
      switch (call.method) {
        case 'onLog':
          final msg = call.arguments as String?;
          if (msg != null && mounted) {
            _appendLog(msg);
          }
          break;
        case 'onProgress':
          final map = call.arguments as Map<dynamic, dynamic>?;
          if (map != null && mounted) {
            final pct = (map['progress'] as num?)?.toDouble() ?? 0.0;
            final text = map['text'] as String? ?? '';
            setState(() {
              _progressPct = pct.clamp(0.0, 100.0);
              _statusMessage = text;
            });
          }
          break;
        case 'onFinished':
          final map = call.arguments as Map<dynamic, dynamic>?;
          final success = map?['success'] as bool? ?? false;
          final msg = map?['message'] as String? ?? '';
          if (mounted) {
            setState(() {
              _isBusy = false;
              _currentTaskMode = 'none';
              _statusMessage = msg;
            });
            _showNotificationSnackBar(
              success ? 'Operação concluída com sucesso!' : 'Operação finalizada.',
              isError: !success,
            );
          }
          break;
      }
    });
  }

  Future<void> _initAppEnvironment() async {
    _appendLog('[Sistema] Inicializando ambiente do YTDawn Mobile...');
    try {
      final appDir = await getApplicationDocumentsDirectory();
      var cookieFile = File('${appDir.path}/cookies.txt');
      if (!await cookieFile.exists() || await cookieFile.length() < 50) {
        final pubCookie = File('/storage/emulated/0/Download/YTDawn/cookies.txt');
        if (await pubCookie.exists() && await pubCookie.length() > 50) {
          cookieFile = pubCookie;
        }
      }
      if (await cookieFile.exists() && await cookieFile.length() > 50) {
        setState(() {
          _cookiesFilePath = cookieFile.path;
          _hasActiveCookies = true;
        });
        _appendLog('[Cookies] Arquivo cookies.txt carregado (${await cookieFile.length()} bytes).');
      }

      // Inicializa engine nativa no Android
      await platform.invokeMethod('initEngine');

      // Obtém diretório público de downloads
      final dir = await platform.invokeMethod<String>('getDownloadDir');
      if (dir != null && mounted) {
        setState(() {
          _downloadDirectory = dir;
        });
        _appendLog('[Armazenamento] Pasta de destino configurada: $_downloadDirectory');
      }
    } catch (e) {
      _appendLog('[Aviso] Inicialização: $e');
    }
  }

  void _appendLog(String line) {
    if (!mounted) return;
    setState(() {
      _logs.add(line);
      if (_logs.length > 500) {
        _logs.removeRange(0, 100);
      }
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_logScrollController.hasClients) {
        _logScrollController.animateTo(
          _logScrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _showNotificationSnackBar(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          message,
          style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white),
        ),
        backgroundColor: isError ? Colors.redAccent.shade700 : const Color(0xFF26D0CE),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        duration: const Duration(seconds: 3),
      ),
    );
  }

  // ==================== AÇÕES DE DOWNLOAD ====================

  Future<void> _toggleDownload() async {
    if (_isBusy) {
      await platform.invokeMethod('cancelTask');
      setState(() {
        _isBusy = false;
        _currentTaskMode = 'none';
        _statusMessage = 'Cancelamento solicitado...';
      });
      return;
    }

    final rawText = _urlsController.text.trim();
    if (rawText.isEmpty) {
      _showNotificationSnackBar('Cole pelo menos um link para download.', isError: true);
      return;
    }

    final urls = rawText
        .split('\n')
        .map((u) => u.trim())
        .where((u) => u.startsWith('http://') || u.startsWith('https://'))
        .toList();

    if (urls.isEmpty) {
      _showNotificationSnackBar('Nenhum link válido encontrado (deve iniciar com http).', isError: true);
      return;
    }

    // Fecha o teclado ao iniciar
    FocusScope.of(context).unfocus();

    setState(() {
      _isBusy = true;
      _currentTaskMode = 'download';
      _progressPct = 0.0;
      _statusMessage = 'Iniciando download...';
    });

    try {
      await platform.invokeMethod('startDownload', {
        'urls': urls,
        'format': _dlFormat,
        'resolution': _dlResolution,
        'compression': _dlCompression,
        'cookiesPath': _cookiesFilePath,
        'outputDir': _downloadDirectory,
      });
    } catch (e) {
      _appendLog('[ERRO] Falha ao iniciar download: $e');
      setState(() {
        _isBusy = false;
        _currentTaskMode = 'none';
      });
    }
  }

  // ==================== AÇÕES DE CONVERSÃO ====================

  Future<void> _pickFileForConversion() async {
    try {
      final files = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['mp4', 'mkv', 'avi', 'mov', 'webm', 'flv', 'mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a'],
      );

      if (files.isNotEmpty && files.first.path != null) {
        final path = files.first.path!;
        final file = File(path);
        final size = await file.length();
        setState(() {
          _selectedConvertFilePath = path;
          _selectedConvertFileSize = size;
        });
        _appendLog('[Arquivo] Selecionado para conversão: ${file.path.split(Platform.pathSeparator).last} (${(size / (1024 * 1024)).toStringAsFixed(1)} MB)');
      }
    } catch (e) {
      _appendLog('[ERRO] Falha ao selecionar arquivo: $e');
    }
  }

  Future<void> _toggleConversion() async {
    if (_isBusy) {
      await platform.invokeMethod('cancelTask');
      setState(() {
        _isBusy = false;
        _currentTaskMode = 'none';
        _statusMessage = 'Cancelamento solicitado...';
      });
      return;
    }

    if (_selectedConvertFilePath == null || !File(_selectedConvertFilePath!).existsSync()) {
      _showNotificationSnackBar('Selecione um arquivo de mídia válido primeiro.', isError: true);
      return;
    }

    FocusScope.of(context).unfocus();

    setState(() {
      _isBusy = true;
      _currentTaskMode = 'convert';
      _progressPct = 0.0;
      _statusMessage = 'Iniciando conversão FFmpeg...';
    });

    try {
      await platform.invokeMethod('startConversion', {
        'inputPath': _selectedConvertFilePath,
        'format': _convFormat,
        'compression': _convCompression,
        'outputDir': _downloadDirectory,
      });
    } catch (e) {
      _appendLog('[ERRO] Falha na conversão: $e');
      setState(() {
        _isBusy = false;
        _currentTaskMode = 'none';
      });
    }
  }

  // ==================== YOUTUBE LOGIN & COOKIES ====================

  void _openYouTubeLoginModal() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => YouTubeLoginSheet(
        onCookiesSaved: (filePath) {
          setState(() {
            _cookiesFilePath = filePath;
            _hasActiveCookies = true;
          });
          _appendLog('✅ [Cookies] Conta do YouTube conectada e cookies extraídos com sucesso!');
          _showNotificationSnackBar('Conta do YouTube vinculada com sucesso!');
        },
      ),
    );
  }

  Future<void> _clearAppCache() async {
    _appendLog('[Sistema] Limpando cache e atualizando engine...');
    try {
      await platform.invokeMethod('clearCache');
      await platform.invokeMethod('updateEngine');
      _showNotificationSnackBar('Cache limpo e engine atualizada!');
    } catch (e) {
      _appendLog('[ERRO] Ao limpar cache: $e');
    }
  }

  void _showDownloadedFiles() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF181332),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => DownloadedFilesSheet(downloadDir: _downloadDirectory),
    );
  }

  // ==================== BUILD UI RESPONSIVA COM SCROLL COMPLETO ====================

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        child: SingleChildScrollView(
          controller: _mainScrollController,
          physics: const BouncingScrollPhysics(),
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(context).viewInsets.bottom + 20,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildHeader(),
              _buildTabBar(),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 200),
                child: _activeTabIndex == 0 ? _buildDownloadTab() : _buildConvertTab(),
              ),
              _buildProgressAndStatusPanel(),
              _buildLogConsole(),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  // Cabeçalho Aurora
  Widget _buildHeader() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF181332),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF342858), width: 1),
      ),
      child: Column(
        children: [
          Row(
            children: [
              // Logo Aurora Dawn
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: Image.asset(
                  'assets/icon.png',
                  width: 44,
                  height: 44,
                  errorBuilder: (context, error, stackTrace) => Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFFFF8C42), Color(0xFFEA3A8E)],
                      ),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.wb_sunny_rounded, color: Colors.white, size: 28),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              // Título e Subtítulo
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: const [
                    Text(
                      'YTDawn',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFFFF8C42),
                        letterSpacing: 0.5,
                      ),
                    ),
                    SizedBox(height: 2),
                    Text(
                      'Portable Media Downloader & FFmpeg',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF26D0CE),
                      ),
                    ),
                  ],
                ),
              ),
              // Botões Rápidos do Cabeçalho
              _buildHeaderButton(
                icon: Icons.cookie_rounded,
                label: _hasActiveCookies ? 'Cookies Ativos' : 'Login YT',
                color: _hasActiveCookies ? const Color(0xFF26D0CE) : const Color(0xFFFF8C42),
                onTap: _openYouTubeLoginModal,
              ),
              const SizedBox(width: 6),
              _buildHeaderButton(
                icon: Icons.cleaning_services_rounded,
                label: 'Cache',
                color: const Color(0xFFFFCC00),
                onTap: _clearAppCache,
              ),
              const SizedBox(width: 6),
              _buildHeaderButton(
                icon: Icons.folder_open_rounded,
                label: 'Pasta',
                color: const Color(0xFFEA3A8E),
                onTap: _showDownloadedFiles,
              ),
            ],
          ),
          const SizedBox(height: 8),
          // Badges das redes sociais suportadas
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _buildSocialBadge('YouTube', const Color(0xFFFF3333)),
                _buildSocialBadge('Instagram', const Color(0xFFE1306C)),
                _buildSocialBadge('TikTok', const Color(0xFF00F2FE)),
                _buildSocialBadge('Facebook', const Color(0xFF1877F2)),
                _buildSocialBadge('X / Twitter', const Color(0xFF1DA1F2)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeaderButton({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        decoration: BoxDecoration(
          color: const Color(0xFF2B204E),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withAlpha(100), width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSocialBadge(String name, Color dotColor) {
    return Container(
      margin: const EdgeInsets.only(right: 6),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: const Color(0xFF231A44),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle),
          ),
          const SizedBox(width: 5),
          Text(
            name,
            style: const TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.bold,
              color: Colors.white70,
            ),
          ),
        ],
      ),
    );
  }

  // Segmented Tabs com alternância direta
  Widget _buildTabBar() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      height: 40,
      decoration: BoxDecoration(
        color: const Color(0xFF100C22),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Expanded(
            child: InkWell(
              onTap: () => setState(() => _activeTabIndex = 0),
              borderRadius: BorderRadius.circular(8),
              child: Container(
                decoration: BoxDecoration(
                  color: _activeTabIndex == 0 ? const Color(0xFFEA3A8E) : Colors.transparent,
                  borderRadius: BorderRadius.circular(8),
                ),
                alignment: Alignment.center,
                child: Text(
                  'Download',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    color: _activeTabIndex == 0 ? Colors.white : const Color(0xFF9D95C4),
                  ),
                ),
              ),
            ),
          ),
          Expanded(
            child: InkWell(
              onTap: () => setState(() => _activeTabIndex = 1),
              borderRadius: BorderRadius.circular(8),
              child: Container(
                decoration: BoxDecoration(
                  color: _activeTabIndex == 1 ? const Color(0xFFEA3A8E) : Colors.transparent,
                  borderRadius: BorderRadius.circular(8),
                ),
                alignment: Alignment.center,
                child: Text(
                  'Conversão',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    color: _activeTabIndex == 1 ? Colors.white : const Color(0xFF9D95C4),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ==================== ABA 1: DOWNLOAD ====================

  Widget _buildDownloadTab() {
    final isAudio = _dlFormat.contains('MP3');

    return Padding(
      key: const ValueKey('tab_download'),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Links de Mídia (um por linha):',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFFE0DAF7)),
              ),
              Row(
                children: [
                  TextButton.icon(
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
                      minimumSize: const Size(50, 24),
                    ),
                    icon: const Icon(Icons.content_paste_rounded, size: 13, color: Color(0xFF26D0CE)),
                    label: const Text('Colar', style: TextStyle(fontSize: 11, color: Color(0xFF26D0CE))),
                    onPressed: () async {
                      final data = await Clipboard.getData(Clipboard.kTextPlain);
                      if (data?.text != null && data!.text!.isNotEmpty) {
                        _urlsController.text = data.text!;
                      }
                    },
                  ),
                  TextButton(
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 0),
                      minimumSize: const Size(40, 24),
                    ),
                    child: const Text('Limpar', style: TextStyle(fontSize: 11, color: Color(0xFF9D95C4))),
                    onPressed: () => _urlsController.clear(),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 4),
          // Caixa de Texto dos URLs
          Container(
            decoration: BoxDecoration(
              color: const Color(0xFF100B21),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF342858), width: 1),
            ),
            child: TextField(
              controller: _urlsController,
              maxLines: 3,
              style: const TextStyle(fontSize: 12, color: Colors.white),
              decoration: const InputDecoration(
                hintText: 'https://www.youtube.com/watch?v=...\nhttps://instagram.com/reel/...\nhttps://tiktok.com/@...',
                hintStyle: TextStyle(fontSize: 11, color: Color(0xFF5A527A)),
                border: InputBorder.none,
                contentPadding: EdgeInsets.all(10),
              ),
            ),
          ),
          const SizedBox(height: 10),

          // Configurações: Formato + Resolução + Compressão
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFF181332),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFF28204B)),
            ),
            child: Column(
              children: [
                // Linha 1: Formato
                Row(
                  children: [
                    const SizedBox(
                      width: 75,
                      child: Text('Formato:', style: TextStyle(fontSize: 12, color: Color(0xFFC7BEE6))),
                    ),
                    Expanded(
                      child: Container(
                        height: 34,
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEA3A8E),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<String>(
                            value: _dlFormat,
                            isExpanded: true,
                            dropdownColor: const Color(0xFF181332),
                            icon: const Icon(Icons.arrow_drop_down, color: Colors.white),
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white),
                            items: const [
                              DropdownMenuItem(value: 'MP4 (Vídeo)', child: Text('MP4 (Vídeo)')),
                              DropdownMenuItem(value: 'MP3 (Áudio)', child: Text('MP3 (Áudio)')),
                            ],
                            onChanged: (val) {
                              if (val != null) setState(() => _dlFormat = val);
                            },
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),

                // Linha 2: Resolução (1080p / 720p)
                Opacity(
                  opacity: isAudio ? 0.35 : 1.0,
                  child: Row(
                    children: [
                      const SizedBox(
                        width: 75,
                        child: Text('Resolução:', style: TextStyle(fontSize: 12, color: Color(0xFFC7BEE6))),
                      ),
                      _buildRadioOption('1080p', _dlResolution, const Color(0xFF26D0CE), isAudio ? null : (v) {
                        setState(() => _dlResolution = v);
                      }),
                      const SizedBox(width: 14),
                      _buildRadioOption('720p', _dlResolution, const Color(0xFF26D0CE), isAudio ? null : (v) {
                        setState(() => _dlResolution = v);
                      }),
                    ],
                  ),
                ),
                const SizedBox(height: 8),

                // Linha 3: Compressão (None / Full / Half)
                Opacity(
                  opacity: isAudio ? 0.35 : 1.0,
                  child: Row(
                    children: [
                      const SizedBox(
                        width: 75,
                        child: Text('Compressão:', style: TextStyle(fontSize: 12, color: Color(0xFFC7BEE6))),
                      ),
                      _buildRadioOption('None', _dlCompression, const Color(0xFF9D95C4), isAudio ? null : (v) {
                        setState(() => _dlCompression = v);
                      }),
                      const SizedBox(width: 8),
                      _buildRadioOption('Full (80%)', _dlCompression, const Color(0xFFFF8C42), isAudio ? null : (_) {
                        setState(() => _dlCompression = 'Full');
                      }, isSelected: _dlCompression == 'Full'),
                      const SizedBox(width: 8),
                      _buildRadioOption('Half (50%)', _dlCompression, const Color(0xFFEA3A8E), isAudio ? null : (_) {
                        setState(() => _dlCompression = 'Half');
                      }, isSelected: _dlCompression == 'Half'),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),

          // Botão Grande de Ação: Iniciar / Cancelar
          SizedBox(
            width: double.infinity,
            height: 44,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: _isBusy && _currentTaskMode == 'download'
                    ? const Color(0xFFFF3333)
                    : const Color(0xFFFF8C42),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                elevation: 3,
              ),
              icon: Icon(
                _isBusy && _currentTaskMode == 'download' ? Icons.stop_rounded : Icons.download_rounded,
                color: Colors.white,
              ),
              label: Text(
                _isBusy && _currentTaskMode == 'download' ? 'Cancelar download' : 'Iniciar download',
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.white),
              ),
              onPressed: _isBusy && _currentTaskMode != 'download' ? null : _toggleDownload,
            ),
          ),
        ],
      ),
    );
  }

  // ==================== ABA 2: CONVERSÃO ====================

  Widget _buildConvertTab() {
    return Padding(
      key: const ValueKey('tab_convert'),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Selecione o arquivo de mídia local para conversão com FFmpeg:',
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFFE0DAF7)),
          ),
          const SizedBox(height: 6),

          // Seletor de Arquivo
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFF100B21),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF342858)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    _selectedConvertFilePath != null
                        ? '${_selectedConvertFilePath!.split(Platform.pathSeparator).last} (${(_selectedConvertFileSize! / (1024 * 1024)).toStringAsFixed(1)} MB)'
                        : 'Nenhum arquivo selecionado...',
                    style: TextStyle(
                      fontSize: 12,
                      color: _selectedConvertFilePath != null ? Colors.white : const Color(0xFF5A527A),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF26D0CE),
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    minimumSize: const Size(80, 32),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: const Icon(Icons.file_upload_outlined, size: 15, color: Color(0xFF0D1B2A)),
                  label: const Text(
                    'Selecionar',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF0D1B2A)),
                  ),
                  onPressed: _pickFileForConversion,
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),

          // Opções de Conversão
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFF181332),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFF28204B)),
            ),
            child: Column(
              children: [
                // Formato de Destino
                Row(
                  children: [
                    const SizedBox(
                      width: 90,
                      child: Text('Converter para:', style: TextStyle(fontSize: 12, color: Color(0xFFC7BEE6))),
                    ),
                    Expanded(
                      child: Container(
                        height: 34,
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEA3A8E),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<String>(
                            value: _convFormat,
                            isExpanded: true,
                            dropdownColor: const Color(0xFF181332),
                            icon: const Icon(Icons.arrow_drop_down, color: Colors.white),
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white),
                            items: const [
                              DropdownMenuItem(value: 'MP4', child: Text('MP4 (Vídeo H.264)')),
                              DropdownMenuItem(value: 'MKV', child: Text('MKV (Matroska)')),
                              DropdownMenuItem(value: 'MP3', child: Text('MP3 (Áudio)')),
                              DropdownMenuItem(value: 'WAV', child: Text('WAV (Lossless)')),
                              DropdownMenuItem(value: 'FLAC', child: Text('FLAC (Lossless)')),
                              DropdownMenuItem(value: 'AAC', child: Text('AAC')),
                              DropdownMenuItem(value: 'OGG', child: Text('OGG (Vorbis)')),
                              DropdownMenuItem(value: 'WEBM', child: Text('WEBM')),
                              DropdownMenuItem(value: 'AVI', child: Text('AVI')),
                              DropdownMenuItem(value: 'GIF', child: Text('GIF (Animado)')),
                            ],
                            onChanged: (val) {
                              if (val != null) setState(() => _convFormat = val);
                            },
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),

                // Compressão na Conversão
                Row(
                  children: [
                    const SizedBox(
                      width: 90,
                      child: Text('Compressão:', style: TextStyle(fontSize: 12, color: Color(0xFFC7BEE6))),
                    ),
                    _buildRadioOption('None', _convCompression, const Color(0xFF9D95C4), (v) {
                      setState(() => _convCompression = v);
                    }),
                    const SizedBox(width: 8),
                    _buildRadioOption('Full (80%)', _convCompression, const Color(0xFFFF8C42), (_) {
                      setState(() => _convCompression = 'Full');
                    }, isSelected: _convCompression == 'Full'),
                    const SizedBox(width: 8),
                    _buildRadioOption('Half (50%)', _convCompression, const Color(0xFFEA3A8E), (_) {
                      setState(() => _convCompression = 'Half');
                    }, isSelected: _convCompression == 'Half'),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),

          // Botão Grande de Ação: Iniciar / Cancelar
          SizedBox(
            width: double.infinity,
            height: 44,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: _isBusy && _currentTaskMode == 'convert'
                    ? const Color(0xFFFF3333)
                    : const Color(0xFF26D0CE),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                elevation: 3,
              ),
              icon: Icon(
                _isBusy && _currentTaskMode == 'convert' ? Icons.stop_rounded : Icons.transform_rounded,
                color: const Color(0xFF0D1B2A),
              ),
              label: Text(
                _isBusy && _currentTaskMode == 'convert' ? 'Cancelar conversão' : 'Iniciar conversão',
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Color(0xFF0D1B2A)),
              ),
              onPressed: _isBusy && _currentTaskMode != 'convert' ? null : _toggleConversion,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRadioOption(
    String label,
    String currentValue,
    Color activeColor,
    ValueChanged<String>? onChanged, {
    bool? isSelected,
  }) {
    final selected = isSelected ?? (currentValue == label);
    return InkWell(
      onTap: onChanged != null ? () => onChanged(label) : null,
      borderRadius: BorderRadius.circular(6),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 14,
            height: 14,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: selected ? activeColor : const Color(0xFF5A527A),
                width: 2,
              ),
            ),
            child: selected
                ? Center(
                    child: Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: activeColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                  )
                : null,
          ),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: selected ? Colors.white : const Color(0xFF9D95C4),
            ),
          ),
        ],
      ),
    );
  }

  // ==================== PAINEL DE STATUS & PROGRESSO ====================

  Widget _buildProgressAndStatusPanel() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFF181332),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF28204B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  _statusMessage,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFFE0DAF7),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Text(
                '${_progressPct.toStringAsFixed(1)}%',
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF26D0CE),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: _progressPct / 100.0,
              minHeight: 7,
              backgroundColor: const Color(0xFF100C22),
              valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFFEA3A8E)),
            ),
          ),
        ],
      ),
    );
  }

  // ==================== CONSOLE DE LOGS ====================

  Widget _buildLogConsole() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      height: 130,
      decoration: BoxDecoration(
        color: const Color(0xFF0C071E),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF342858)),
      ),
      child: Column(
        children: [
          // Barra de título do log
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: const BoxDecoration(
              color: Color(0xFF181332),
              borderRadius: BorderRadius.vertical(top: Radius.circular(9)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Row(
                  children: [
                    Icon(Icons.terminal_rounded, size: 12, color: Color(0xFF26D0CE)),
                    SizedBox(width: 5),
                    Text(
                      'Terminal de Log',
                      style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF26D0CE)),
                    ),
                  ],
                ),
                Row(
                  children: [
                    InkWell(
                      onTap: () {
                        Clipboard.setData(ClipboardData(text: _logs.join('\n')));
                        _showNotificationSnackBar('Logs copiados!');
                      },
                      child: const Text('Copiar', style: TextStyle(fontSize: 10, color: Color(0xFF9D95C4))),
                    ),
                    const SizedBox(width: 10),
                    InkWell(
                      onTap: () => setState(() => _logs.clear()),
                      child: const Text('Limpar', style: TextStyle(fontSize: 10, color: Color(0xFFFF8C42))),
                    ),
                  ],
                ),
              ],
            ),
          ),
          // Lista de Logs
          Expanded(
            child: ListView.builder(
              controller: _logScrollController,
              physics: const ClampingScrollPhysics(),
              padding: const EdgeInsets.all(6),
              itemCount: _logs.length,
              itemBuilder: (ctx, idx) {
                final line = _logs[idx];
                Color lineColor = const Color(0xFFDCD5F3);
                if (line.contains('[ERRO]')) {
                  lineColor = Colors.redAccent;
                } else if (line.contains('[SUCESSO]')) {
                  lineColor = Colors.greenAccent;
                } else if (line.contains('[Cookies]')) {
                  lineColor = const Color(0xFFFF8C42);
                } else if (line.contains('[Sistema]') || line.contains('[Atualização]')) {
                  lineColor = const Color(0xFF26D0CE);
                } else if (line.contains('[FFmpeg]')) {
                  lineColor = const Color(0xFFEA3A8E);
                }

                return Text(
                  line,
                  style: TextStyle(
                    fontSize: 9.5,
                    fontFamily: 'monospace',
                    color: lineColor,
                    height: 1.3,
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

// ==================== MODAL DE LOGIN DO YOUTUBE ====================

class YouTubeLoginSheet extends StatefulWidget {
  final ValueChanged<String> onCookiesSaved;

  const YouTubeLoginSheet({super.key, required this.onCookiesSaved});

  @override
  State<YouTubeLoginSheet> createState() => _YouTubeLoginSheetState();
}

class _YouTubeLoginSheetState extends State<YouTubeLoginSheet> {
  double _loadProgress = 0.0;
  bool _isExtracting = false;
  String _statusText = 'Faça login no Google/YouTube abaixo para gerar cookies';
  Timer? _cookieCheckTimer;

  @override
  void initState() {
    super.initState();
    _cookieCheckTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (mounted) {
        _checkAndExtractCookies(silent: true);
      }
    });
  }

  @override
  void dispose() {
    _cookieCheckTimer?.cancel();
    super.dispose();
  }

  Future<void> _checkAndExtractCookies({bool silent = false}) async {
    if (_isExtracting) return;
    try {
      final cookieManager = CookieManager.instance();
      final cookies = await cookieManager.getCookies(url: WebUri('https://www.youtube.com'));

      bool hasAuthCookie = false;
      for (final c in cookies) {
        if (c.name == 'LOGIN_INFO' ||
            c.name == 'SID' ||
            c.name == '__Secure-3PSID' ||
            c.name == '__Secure-1PSID' ||
            c.name == 'SAPISID') {
          hasAuthCookie = true;
          break;
        }
      }

      if (hasAuthCookie) {
        if (mounted) {
          setState(() {
            _statusText = 'Login detectado! Gerando cookies.txt...';
            _isExtracting = true;
          });
        }

        final netscapeBuffer = StringBuffer();
        netscapeBuffer.writeln('# Netscape HTTP Cookie File');
        netscapeBuffer.writeln('# https://curl.se/docs/http-cookies.html');
        netscapeBuffer.writeln('# Automatically generated by YTDawn Mobile in-app login');
        netscapeBuffer.writeln();

        for (final c in cookies) {
          var domain = c.domain ?? '.youtube.com';
          if (!domain.startsWith('.')) domain = '.$domain';
          final flag = domain.startsWith('.') ? 'TRUE' : 'FALSE';
          final path = (c.path != null && c.path!.isNotEmpty) ? c.path! : '/';
          final secure = (c.isSecure ?? true) ? 'TRUE' : 'FALSE';
          final expires = (c.expiresDate != null)
              ? (c.expiresDate! ~/ 1000)
              : ((DateTime.now().millisecondsSinceEpoch ~/ 1000) + 31536000);
          final name = c.name;
          final value = c.value;

          netscapeBuffer.writeln('$domain\t$flag\t$path\t$secure\t$expires\t$name\t$value');
        }

        final content = netscapeBuffer.toString();

        final appDir = await getApplicationDocumentsDirectory();
        final cookieFile = File('${appDir.path}/cookies.txt');
        await cookieFile.writeAsString(content);

        try {
          final pubDir = Directory('/storage/emulated/0/Download/YTDawn');
          if (await pubDir.exists()) {
            final pubFile = File('${pubDir.path}/cookies.txt');
            await pubFile.writeAsString(content);
          }
        } catch (_) {}

        widget.onCookiesSaved(cookieFile.path);

        if (mounted) {
          Navigator.of(context).pop();
        }
      } else if (!silent && mounted) {
        setState(() {
          _statusText = 'Ainda não autenticado. Conclua o login na página do YouTube.';
        });
      }
    } catch (e) {
      if (!silent && mounted) {
        setState(() {
          _statusText = 'Erro ao verificar cookies: $e';
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _isExtracting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.90,
      decoration: const BoxDecoration(
        color: Color(0xFF181332),
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        children: [
          // Barra de Título do Modal
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: const BoxDecoration(
              color: Color(0xFF231A44),
              borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
            ),
            child: Row(
              children: [
                const Icon(Icons.cookie_rounded, color: Color(0xFFFF8C42), size: 22),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Conectar Conta do YouTube',
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white),
                      ),
                      Text(
                        _statusText,
                        style: const TextStyle(fontSize: 10, color: Color(0xFF26D0CE)),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFFF8C42),
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    minimumSize: const Size(60, 32),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: _isExtracting
                      ? const SizedBox(
                          width: 12,
                          height: 12,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.save_rounded, size: 14, color: Colors.white),
                  label: const Text(
                    'Extrair',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                  onPressed: _isExtracting ? null : () => _checkAndExtractCookies(silent: false),
                ),
                const SizedBox(width: 6),
                IconButton(
                  icon: const Icon(Icons.close_rounded, color: Colors.white70, size: 20),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ),
          if (_loadProgress < 1.0)
            LinearProgressIndicator(
              value: _loadProgress,
              minHeight: 3,
              backgroundColor: const Color(0xFF100C22),
              valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFFEA3A8E)),
            ),
          // WebView com a página de Login do YouTube
          Expanded(
            child: InAppWebView(
              initialUrlRequest: URLRequest(
                url: WebUri('https://accounts.google.com/ServiceLogin?service=youtube&continue=https://www.youtube.com'),
              ),
              initialSettings: InAppWebViewSettings(
                userAgent: 'Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36',
                javaScriptEnabled: true,
                domStorageEnabled: true,
                databaseEnabled: true,
                cacheEnabled: true,
                thirdPartyCookiesEnabled: true,
              ),
              onProgressChanged: (controller, progress) {
                if (mounted) {
                  setState(() {
                    _loadProgress = progress / 100.0;
                  });
                }
              },
              onLoadStop: (controller, url) async {
                if (mounted) {
                  await _checkAndExtractCookies(silent: true);
                }
              },
            ),
          ),
        ],
      ),
    );
  }
}

// ==================== MODAL DE ARQUIVOS BAIXADOS ====================

class DownloadedFilesSheet extends StatefulWidget {
  final String downloadDir;

  const DownloadedFilesSheet({super.key, required this.downloadDir});

  @override
  State<DownloadedFilesSheet> createState() => _DownloadedFilesSheetState();
}

class _DownloadedFilesSheetState extends State<DownloadedFilesSheet> {
  List<FileSystemEntity> _files = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadFiles();
  }

  Future<void> _loadFiles() async {
    try {
      final dir = Directory(widget.downloadDir);
      if (await dir.exists()) {
        final list = await dir.list().toList();
        list.sort((a, b) => b.statSync().modified.compareTo(a.statSync().modified));
        setState(() {
          _files = list.where((f) => f is File && !f.path.endsWith('.txt')).toList();
          _loading = false;
        });
      } else {
        setState(() => _loading = false);
      }
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.65,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Row(
                children: [
                  Icon(Icons.folder_special_rounded, color: Color(0xFF26D0CE), size: 22),
                  SizedBox(width: 8),
                  Text(
                    'Arquivos em Download/YTDawn',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                ],
              ),
              IconButton(
                icon: const Icon(Icons.close_rounded, color: Colors.white70),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFFEA3A8E)))
                : _files.isEmpty
                    ? const Center(
                        child: Text(
                          'Nenhum arquivo baixado ainda.\nEles aparecerão aqui e na pasta Downloads do seu aparelho.',
                          textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 12, color: Color(0xFF9D95C4)),
                        ),
                      )
                    : ListView.separated(
                        itemCount: _files.length,
                        separatorBuilder: (context, index) => const Divider(color: Color(0xFF28204B), height: 1),
                        itemBuilder: (ctx, idx) {
                          final file = _files[idx] as File;
                          final name = file.path.split(Platform.pathSeparator).last;
                          final sizeMb = (file.lengthSync() / (1024 * 1024)).toStringAsFixed(1);
                          final isVideo = name.endsWith('.mp4') || name.endsWith('.mkv') || name.endsWith('.webm');

                          return ListTile(
                            contentPadding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                            leading: Container(
                              width: 36,
                              height: 36,
                              decoration: BoxDecoration(
                                color: isVideo ? const Color(0xFFEA3A8E).withAlpha(50) : const Color(0xFF26D0CE).withAlpha(50),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Icon(
                                isVideo ? Icons.movie_outlined : Icons.music_note_rounded,
                                color: isVideo ? const Color(0xFFEA3A8E) : const Color(0xFF26D0CE),
                                size: 20,
                              ),
                            ),
                            title: Text(
                              name,
                              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text(
                              '$sizeMb MB',
                              style: const TextStyle(fontSize: 10, color: Color(0xFF9D95C4)),
                            ),
                            trailing: IconButton(
                              icon: const Icon(Icons.share_rounded, size: 18, color: Color(0xFFFF8C42)),
                              onPressed: () {
                                SharePlus.instance.share(
                                  ShareParams(files: [XFile(file.path)], subject: name),
                                );
                              },
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
