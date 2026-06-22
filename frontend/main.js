import { app, BrowserWindow, ipcMain, dialog, Menu, Tray, shell } from 'electron';
import fs from 'fs';
import path from 'path';
import isDev from 'electron-is-dev';
import { fileURLToPath } from 'url';
import { execFileSync, spawn } from 'child_process';

let backendProcess = null;
let backendPid = null;
let isBackendStopping = false;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const electronLogDir = path.join(__dirname, '..', 'logs');
const electronLogFile = path.join(electronLogDir, 'electron-main.log');
const ELECTRON_LOG_MAX_BYTES = 5 * 1024 * 1024;
const ELECTRON_LOG_BACKUP_COUNT = 5;
let mainWindow = null;
let appTray = null;
let isQuitting = false;
let isCloseRequestPending = false;
let trayMenu = null;
const MIN_WINDOW_WIDTH = 1366;
const MIN_WINDOW_HEIGHT = 768;

function safeSerialize(value) {
  try {
    if (value instanceof Error) {
      return {
        name: value.name,
        message: value.message,
        stack: value.stack,
      };
    }
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

const logQueue = [];
let isProcessingLogQueue = false;

async function rotateElectronLogIfNeeded(nextLineBytes) {
  try {
    const exists = await fs.promises.access(electronLogFile).then(() => true).catch(() => false);
    if (!exists) {
      return;
    }
    const stat = await fs.promises.stat(electronLogFile);
    if (stat.size + nextLineBytes < ELECTRON_LOG_MAX_BYTES) {
      return;
    }

    const oldest = `${electronLogFile}.${ELECTRON_LOG_BACKUP_COUNT}`;
    const oldestExists = await fs.promises.access(oldest).then(() => true).catch(() => false);
    if (oldestExists) {
      await fs.promises.unlink(oldest);
    }
    for (let index = ELECTRON_LOG_BACKUP_COUNT - 1; index >= 1; index -= 1) {
      const from = `${electronLogFile}.${index}`;
      const to = `${electronLogFile}.${index + 1}`;
      const fromExists = await fs.promises.access(from).then(() => true).catch(() => false);
      if (fromExists) {
        await fs.promises.rename(from, to);
      }
    }
    await fs.promises.rename(electronLogFile, `${electronLogFile}.1`);
  } catch (err) {
    console.error('Log rotation failed:', err);
  }
}

async function processLogQueue() {
  if (isProcessingLogQueue) {
    return;
  }
  isProcessingLogQueue = true;

  try {
    await fs.promises.mkdir(electronLogDir, { recursive: true });

    while (logQueue.length > 0) {
      const line = logQueue.shift();
      const lineBytes = Buffer.byteLength(line, 'utf8');
      try {
        await rotateElectronLogIfNeeded(lineBytes);
        await fs.promises.appendFile(electronLogFile, line, 'utf8');
      } catch (err) {
        console.error('Failed to write electron-main log file:', err);
      }
    }
  } catch (err) {
    console.error('Failed to create electron log directory:', err);
  } finally {
    isProcessingLogQueue = false;
  }
}

function writeElectronLog(level, message, details = null) {
  const timestamp = new Date().toISOString();
  const suffix = details == null ? '' : `\n${safeSerialize(details)}`;
  const line = `[${timestamp}] [${level}] ${message}${suffix}\n`;

  logQueue.push(line);
  processLogQueue();

  const logFn = level === 'ERROR' ? console.error : level === 'WARN' ? console.warn : console.log;
  if (details == null) {
    logFn(`[electron-main] ${message}`);
  } else {
    logFn(`[electron-main] ${message}`, details);
  }
}

function stopBackend(reason = 'unknown') {
  if (isDev || isBackendStopping) {
    return;
  }

  const pid = backendPid || backendProcess?.pid;
  if (!pid) {
    return;
  }

  isBackendStopping = true;
  writeElectronLog('INFO', 'Stopping backend process tree', { reason, pid, platform: process.platform });

  try {
    if (process.platform === 'win32') {
      execFileSync('taskkill', ['/pid', String(pid), '/t', '/f'], {
        stdio: 'ignore',
        windowsHide: true,
      });
    } else {
      try {
        process.kill(-pid, 'SIGTERM');
      } catch {
        process.kill(pid, 'SIGTERM');
      }
    }
  } catch (error) {
    writeElectronLog('WARN', 'Backend termination raised an error', {
      reason,
      pid,
      error: safeSerialize(error),
    });
  } finally {
    backendProcess = null;
    backendPid = null;
    isBackendStopping = false;
  }
}

// Reduce long-idle/minimized renderer black-screen risk on Windows/Electron.
app.commandLine.appendSwitch('disable-renderer-backgrounding');
app.commandLine.appendSwitch('disable-background-timer-throttling');

process.on('uncaughtException', (error) => {
  writeElectronLog('ERROR', 'Uncaught exception in Electron main process', error);
});

process.on('unhandledRejection', (reason) => {
  writeElectronLog('ERROR', 'Unhandled promise rejection in Electron main process', reason);
});

let heartbeatTimer = null;
function resetHeartbeatWatchdog() {
  if (heartbeatTimer) {
    clearTimeout(heartbeatTimer);
  }
  // Heartbeats are sent every 30 seconds. Warning triggers if missed for 45 seconds.
  heartbeatTimer = setTimeout(() => {
    writeElectronLog('WARN', 'Watchdog: Renderer heartbeat missed (45s). Renderer might be frozen.', {
      metrics: app.getAppMetrics(),
    });
  }, 45000);
}

// Handler for folder selection dialog
ipcMain.handle('select-folder', async (event, defaultPath) => {
  writeElectronLog('INFO', 'Folder picker opened', { defaultPath: defaultPath || app.getPath('home') });
  const targetWindow = BrowserWindow.fromWebContents(event.sender) || mainWindow;
  const result = await dialog.showOpenDialog(targetWindow, {
    properties: ['openDirectory'],
    defaultPath: defaultPath || app.getPath('home')
  });
  writeElectronLog('INFO', 'Folder picker closed', { canceled: result.canceled, selected: result.filePaths[0] || null });
  if (result.canceled) {
    return null;
  } else {
    return result.filePaths[0];
  }
});

// Handler for file selection dialog
ipcMain.handle('select-file', async (event, defaultPath) => {
  writeElectronLog('INFO', 'File picker opened', { defaultPath: defaultPath || app.getPath('home') });
  const targetWindow = BrowserWindow.fromWebContents(event.sender) || mainWindow;
  const result = await dialog.showOpenDialog(targetWindow, {
    properties: ['openFile'],
    defaultPath: defaultPath || app.getPath('home')
  });
  writeElectronLog('INFO', 'File picker closed', { canceled: result.canceled, selected: result.filePaths[0] || null });
  if (result.canceled) {
    return null;
  } else {
    return result.filePaths[0];
  }
});

ipcMain.handle('show-item-in-folder', async (_event, filePath) => {
  if (!filePath) {
    return { success: false, error: 'Missing file path' };
  }

  try {
    shell.showItemInFolder(filePath);
    return { success: true };
  } catch (error) {
    writeElectronLog('ERROR', 'Failed to show item in folder', { filePath, error });
    return { success: false, error: error?.message || 'Failed to show item in folder' };
  }
});

ipcMain.on('app-restart', () => {
  writeElectronLog('WARN', 'Renderer requested app restart');
  app.relaunch();
  app.exit(0);
});

ipcMain.on('app-quit', () => {
  writeElectronLog('WARN', 'Renderer requested app quit flow');
  if (mainWindow && !mainWindow.isDestroyed()) {
    requestWindowClose(mainWindow, 'quit-button');
    return;
  }
  isQuitting = true;
  app.quit();
});

ipcMain.on('window-minimize', (event) => {
  const targetWindow = BrowserWindow.fromWebContents(event.sender);
  if (!targetWindow || targetWindow.isDestroyed()) {
    return;
  }
  targetWindow.minimize();
});

ipcMain.on('window-maximize-toggle', (event) => {
  const targetWindow = BrowserWindow.fromWebContents(event.sender);
  if (!targetWindow || targetWindow.isDestroyed()) {
    return;
  }
  if (targetWindow.isMaximized()) {
    targetWindow.unmaximize();
    return;
  }
  targetWindow.maximize();
});

ipcMain.on('window-resize-to-minimum', (event) => {
  const targetWindow = BrowserWindow.fromWebContents(event.sender);
  if (!targetWindow || targetWindow.isDestroyed()) {
    return;
  }

  if (targetWindow.isMaximized()) {
    targetWindow.unmaximize();
  }

  targetWindow.setContentSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT);
  targetWindow.center();
});

ipcMain.on('renderer-log', (_event, payload) => {
  writeElectronLog(payload?.level || 'INFO', payload?.message || 'Renderer log', payload?.details || null);
  if (payload?.message === 'Renderer heartbeat') {
    resetHeartbeatWatchdog();
  }
});

ipcMain.on('app-close-response', (_event, payload) => {
  const action = payload?.action;
  const rememberChoice = Boolean(payload?.rememberChoice);

  writeElectronLog('INFO', 'Renderer responded to close prompt', { action, rememberChoice });
  isCloseRequestPending = false;

  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }

  if (action === 'minimize-to-tray') {
    mainWindow.hide();
    return;
  }

  if (action === 'cancel') {
    return;
  }

  if (action === 'quit') {
    isQuitting = true;
    app.quit();
    return;
  }
});


function getWindowIconPath() {
  const isWindows = process.platform === 'win32';
  const relativePath = isWindows
    ? (isDev ? 'public/favicon/icon.ico' : 'build/favicon/icon.ico')
    : (isDev ? 'public/favicon/96x96.png' : 'build/favicon/96x96.png');

  return path.join(__dirname, relativePath);
}

function showMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }

  if (!mainWindow.isMaximized()) {
    mainWindow.maximize();
  }

  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }

  mainWindow.show();
  mainWindow.focus();
}

function ensureTray() {
  if (appTray) {
    return appTray;
  }

  const trayIconPath = getWindowIconPath();
  appTray = new Tray(trayIconPath);
  appTray.setToolTip('SWAYA');
  trayMenu = Menu.buildFromTemplate([
    { label: 'Open SWAYA', click: () => showMainWindow() },
    {
      label: 'Quit SWAYA',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);
  appTray.setContextMenu(trayMenu);
  appTray.on('click', () => {
    if (trayMenu) {
      appTray.popUpContextMenu(trayMenu);
    }
  });
  appTray.on('double-click', () => showMainWindow());

  writeElectronLog('INFO', 'System tray initialized', { trayIconPath });
  return appTray;
}

function requestWindowClose(win, source = 'window-close') {
  if (isQuitting) {
    return;
  }

  if (source === 'window-close') {
    writeElectronLog('INFO', 'Window close redirected to tray');
    win.hide();
    return;
  }

  if (isCloseRequestPending) {
    return;
  }

  isCloseRequestPending = true;
  writeElectronLog('INFO', 'Requesting renderer close decision', { source });
  win.webContents.send('app-close-requested', { source });
}

function createWindow() {
  const iconPath = getWindowIconPath();
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'SWAYA',
    minWidth: MIN_WINDOW_WIDTH,
    minHeight: MIN_WINDOW_HEIGHT,
    useContentSize: true,
    frame: false,
    icon: iconPath,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      backgroundThrottling: false,
    },
    backgroundColor: '#0a0a0a', // Deep black to prevent white flash
    autoHideMenuBar: true,
  });
  mainWindow = win;
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
  win.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT);
  win.maximize();
  win.once('ready-to-show', () => {
    if (!win.isDestroyed() && !win.isMaximized()) {
      win.maximize();
    }
  });
  win.setMenu(null);
  ensureTray();

  writeElectronLog('INFO', 'BrowserWindow created', {
    isDev,
    iconPath,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      backgroundThrottling: false,
    },
  });

  // Load from Vite dev server in development, or build file in production
  let backendPort = 8000;
  const possiblePortPaths = [
    path.join(__dirname, '..', 'port.txt'),
    path.join(__dirname, 'port.txt'),
    path.join(process.resourcesPath, 'backend', 'port.txt'),
  ];
  for (const p of possiblePortPaths) {
    if (fs.existsSync(p)) {
      try {
        const content = fs.readFileSync(p, 'utf8').trim();
        const parsed = parseInt(content, 10);
        if (!isNaN(parsed)) {
          backendPort = parsed;
          break;
        }
      } catch (e) {
        writeElectronLog('WARN', `Failed to read port from ${p}`, e);
      }
    }
  }

  const targetUrl = isDev
    ? `http://localhost:5173?backend_port=${backendPort}`
    : `file://${path.join(__dirname, 'build', 'index.html')}?backend_port=${backendPort}`;
  writeElectronLog('INFO', 'Loading renderer URL', { targetUrl });
  win.loadURL(targetUrl).catch((error) => {
    writeElectronLog('ERROR', 'Failed to load renderer URL', error);
  });

  win.webContents.on('before-input-event', (event, input) => {
    const isReloadShortcut =
      input.type === 'keyDown' && (
        input.key === 'F5' ||
        ((input.control || input.meta) && input.key.toLowerCase() === 'r')
      );

    if (!isReloadShortcut) {
      return;
    }

    event.preventDefault();
    writeElectronLog('INFO', 'Manual reload shortcut triggered', {
      key: input.key,
      control: input.control,
      meta: input.meta,
      shift: input.shift,
    });

    if (input.shift) {
      win.webContents.reloadIgnoringCache();
      return;
    }

    win.webContents.reload();
  });

  if (isDev) {
    win.webContents.openDevTools();
  }

  win.webContents.on('render-process-gone', (_event, details) => {
    writeElectronLog('ERROR', 'Renderer process gone', {
      details,
      url: win.webContents.getURL(),
      isLoading: win.webContents.isLoading(),
      isCrashed: win.webContents.isCrashed(),
    });
    if (!win.isDestroyed()) {
      win.reload();
    }
  });

  win.on('unresponsive', () => {
    writeElectronLog('WARN', 'Window became unresponsive', {
      metrics: app.getAppMetrics(),
    });
    if (!win.isDestroyed()) {
      win.reload();
    }
  });

  win.on('closed', () => {
    writeElectronLog('INFO', 'BrowserWindow closed');
    if (mainWindow === win) {
      mainWindow = null;
    }
  });

  win.on('close', (event) => {
    if (isQuitting) {
      return;
    }

    event.preventDefault();
    requestWindowClose(win, 'window-close');
  });

  win.on('responsive', () => {
    writeElectronLog('INFO', 'Window became responsive again');
  });

  win.webContents.on('dom-ready', () => {
    writeElectronLog('INFO', 'Renderer DOM ready', { url: win.webContents.getURL() });
    isCloseRequestPending = false;
  });

  win.webContents.on('did-finish-load', () => {
    writeElectronLog('INFO', 'Renderer finished load', { url: win.webContents.getURL() });
  });

  win.webContents.on('did-start-loading', () => {
    writeElectronLog('INFO', 'Renderer started loading', { url: win.webContents.getURL() });
  });

  win.webContents.on('did-stop-loading', () => {
    writeElectronLog('INFO', 'Renderer stopped loading', { url: win.webContents.getURL() });
  });

  win.webContents.on('did-start-navigation', (_event, url, isInPlace, isMainFrame, frameProcessId, frameRoutingId) => {
    writeElectronLog('INFO', 'Renderer started navigation', {
      url,
      isInPlace,
      isMainFrame,
      frameProcessId,
      frameRoutingId,
    });
  });

  win.webContents.on('did-navigate', (_event, url, httpResponseCode, httpStatusText) => {
    writeElectronLog('INFO', 'Renderer navigated', {
      url,
      httpResponseCode,
      httpStatusText,
    });
  });

  win.webContents.on('did-navigate-in-page', (_event, url, isMainFrame, frameProcessId, frameRoutingId) => {
    writeElectronLog('INFO', 'Renderer navigated in-page', {
      url,
      isMainFrame,
      frameProcessId,
      frameRoutingId,
    });
  });

  win.webContents.on('console-message', (details) => {
    if (details.level === 'error') {
      writeElectronLog('ERROR', 'Renderer console message', {
        level: details.level,
        message: details.message,
        line: details.lineNumber,
        sourceId: details.sourceId,
      });
    }
  });

  win.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    writeElectronLog('ERROR', 'Renderer failed to load', {
      errorCode,
      errorDescription,
      validatedURL,
      isMainFrame,
    });
  });

  win.webContents.on('crashed', (_event, killed) => {
    writeElectronLog('ERROR', 'WebContents crashed', {
      killed,
      url: win.webContents.getURL(),
      isLoading: win.webContents.isLoading(),
    });
  });
}

function startBackend() {
  if (isDev) {
    writeElectronLog('INFO', 'Dev mode: backend should be started externally.');
    return;
  }

  const isWin = process.platform === 'win32';
  const backendExecutable = isWin ? 'swaya-backend.exe' : 'swaya-backend';
  const backendPath = path.join(
    process.resourcesPath,
    'backend',
    backendExecutable
  );

  writeElectronLog('INFO', `Starting backend from: ${backendPath}`);

  if (!fs.existsSync(backendPath)) {
    writeElectronLog('ERROR', `Backend executable not found at: ${backendPath}`);
    return;
  }

  try {
    backendProcess = spawn(backendPath, [], {
      cwd: path.dirname(backendPath),
      env: { ...process.env },
      stdio: 'ignore',
      detached: process.platform !== 'win32',
      windowsHide: true,
    });
    backendPid = backendProcess.pid ?? null;

    backendProcess.on('error', (err) => {
      writeElectronLog('ERROR', 'Failed to start backend process', err);
    });

    backendProcess.on('exit', (code, signal) => {
      backendProcess = null;
      backendPid = null;
      writeElectronLog('INFO', `Backend process exited with code ${code} and signal ${signal}`);
    });
  } catch (error) {
    writeElectronLog('ERROR', 'Exception starting backend', error);
  }
}

function waitForPortAndCreateWindow() {
  const portFile = isDev
    ? path.join(__dirname, '..', 'port.txt')
    : path.join(process.resourcesPath, 'backend', 'port.txt');

  // Delete old port.txt first if it exists to ensure freshness
  if (fs.existsSync(portFile)) {
    try {
      fs.unlinkSync(portFile);
    } catch (e) {
      writeElectronLog('WARN', 'Could not delete old port.txt', e);
    }
  }

  startBackend();

  let attempts = 0;
  const maxAttempts = 50; // 5 seconds maximum wait time

  function check() {
    if (fs.existsSync(portFile)) {
      try {
        const content = fs.readFileSync(portFile, 'utf8').trim();
        const parsed = parseInt(content, 10);
        if (!isNaN(parsed) && parsed > 0) {
          writeElectronLog('INFO', `Found backend port: ${parsed}`);
          createWindow();
          return;
        }
      } catch (e) {
        writeElectronLog('WARN', 'Error reading port file, retrying', e);
      }
    }
    attempts++;
    if (attempts < maxAttempts) {
      setTimeout(check, 100);
    } else {
      writeElectronLog('ERROR', 'Timed out waiting for backend port.txt, starting window anyway');
      createWindow();
    }
  }

  check();
}

app.whenReady().then(() => {
  writeElectronLog('INFO', 'Electron app ready');
  waitForPortAndCreateWindow();
});

app.on('render-process-gone', (_event, webContents, details) => {
  writeElectronLog('ERROR', 'App-level render-process-gone', {
    details,
    url: webContents?.getURL?.(),
  });
});

app.on('child-process-gone', (_event, details) => {
  writeElectronLog('ERROR', 'Child process gone', details);
});

app.on('browser-window-created', (_event, window) => {
  writeElectronLog('INFO', 'browser-window-created', { id: window.id });
});

app.on('before-quit', () => {
  writeElectronLog('WARN', 'before-quit fired');
  stopBackend('before-quit');
});

app.on('will-quit', () => {
  writeElectronLog('WARN', 'will-quit fired');
  stopBackend('will-quit');
});

app.on('quit', (_event, exitCode) => {
  writeElectronLog('WARN', 'quit fired', { exitCode });
  stopBackend('quit');
});

app.on('window-all-closed', () => {
  writeElectronLog('INFO', 'window-all-closed fired', { platform: process.platform });
  if (process.platform !== 'darwin' && isQuitting) {
    app.quit();
  }
});

app.on('activate', () => {
  writeElectronLog('INFO', 'activate fired', { windowCount: BrowserWindow.getAllWindows().length });
  if (mainWindow && !mainWindow.isDestroyed()) {
    showMainWindow();
  } else if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
