/**
 * Shared utilities for Pop Quiz frontend.
 */

/**
 * Theme manager for light/dark/auto mode.
 */
class ThemeManager {
    constructor() {
        this.STORAGE_KEY = 'pop-quiz-theme';
        this.themes = ['auto', 'light', 'dark'];
        this.currentTheme = this.loadTheme();
        this.systemDarkMode = window.matchMedia('(prefers-color-scheme: dark)');

        this.init();
    }

    loadTheme() {
        const saved = localStorage.getItem(this.STORAGE_KEY);
        return this.themes.includes(saved) ? saved : 'auto';
    }

    saveTheme(theme) {
        localStorage.setItem(this.STORAGE_KEY, theme);
    }

    getEffectiveTheme() {
        if (this.currentTheme === 'auto') {
            return this.systemDarkMode.matches ? 'dark' : 'light';
        }
        return this.currentTheme;
    }

    applyTheme() {
        const effective = this.getEffectiveTheme();
        document.documentElement.setAttribute('data-theme', effective);
        this.updateToggleIcon(this.currentTheme);
    }

    updateToggleIcon(theme) {
        const sunIcon = document.querySelector('.sun-icon');
        const moonIcon = document.querySelector('.moon-icon');
        const autoIcon = document.querySelector('.auto-icon');

        if (theme === 'auto') {
            sunIcon?.classList.add('hidden');
            moonIcon?.classList.add('hidden');
            autoIcon?.classList.remove('hidden');
        } else if (theme === 'dark') {
            sunIcon?.classList.add('hidden');
            moonIcon?.classList.remove('hidden');
            autoIcon?.classList.add('hidden');
        } else {
            sunIcon?.classList.remove('hidden');
            moonIcon?.classList.add('hidden');
            autoIcon?.classList.add('hidden');
        }
    }

    toggle() {
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % this.themes.length;
        this.currentTheme = this.themes[nextIndex];
        this.saveTheme(this.currentTheme);
        this.applyTheme();
    }

    init() {
        // Apply theme immediately (before page render)
        this.applyTheme();

        // Listen for system theme changes
        this.systemDarkMode.addEventListener('change', () => {
            if (this.currentTheme === 'auto') {
                this.applyTheme();
            }
        });

        // Setup toggle button
        const toggleBtn = document.getElementById('theme-toggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggle());
        }
    }
}

// Initialize theme immediately
const themeManager = new ThemeManager();

/**
 * Escape HTML entities to prevent XSS.
 */
function escapeHtml(text) {
    return (text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/**
 * Render simple Markdown (inline code, bold, italic) to HTML.
 */
function renderMarkdown(text) {
    if (!text) return '';
    let result = escapeHtml(text);
    result = result.replace(/`([^`]+)`/g, '<code>$1</code>');
    result = result.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    result = result.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
    return result;
}

/**
 * Interpolate color from green -> yellow -> red based on percentage.
 * 100% = green, 50% = yellow, 0% = red
 */
function getTimerColor(percent) {
    if (percent > 50) {
        const t = (percent - 50) / 50;
        const r = Math.round(46 + (241 - 46) * (1 - t));
        const g = Math.round(204 + (196 - 204) * (1 - t));
        const b = Math.round(113 + (0 - 113) * (1 - t));
        return `rgb(${r}, ${g}, ${b})`;
    } else {
        const t = percent / 50;
        const r = Math.round(231 + (241 - 231) * t);
        const g = Math.round(76 + (196 - 76) * t);
        const b = Math.round(60 + (0 - 60) * t);
        return `rgb(${r}, ${g}, ${b})`;
    }
}

/**
 * Timer manager for question countdowns.
 * Supports both local countdown and server-synchronized timers.
 */
class QuizTimer {
    constructor(progressBarId, timerTextId) {
        this.progressBar = document.getElementById(progressBarId);
        this.timerText = document.getElementById(timerTextId);
        this.timerInterval = null;
        this.progressInterval = null;
        this.endTime = 0;  // Absolute end time (for synced mode)
        this.remaining = 0;  // Remaining seconds (for local mode)
        this.totalTime = 0;  // Total duration in seconds (for synced mode)
    }

    /**
     * Start timer synchronized with server.
     * @param {number} timeRemaining - Seconds remaining from server
     * @param {number} serverTime - Server timestamp when state was sent (optional)
     * @param {function} onComplete - Callback when timer expires
     */
    startSynced(timeRemaining, serverTime = null, onComplete = null, totalTime = null) {
        this.stop();

        // Calculate absolute end time accounting for network latency
        const now = Date.now() / 1000;
        const latencyOffset = serverTime ? (now - serverTime) : 0;
        const adjustedRemaining = Math.max(0, timeRemaining - latencyOffset);

        this.endTime = now + adjustedRemaining;
        this.totalTime = Math.max(
            0,
            totalTime !== null && totalTime !== undefined
                ? totalTime
                : adjustedRemaining
        );

        // Update display immediately
        this.updateDisplay();

        // Update progress bar at 60fps (16ms) for smooth animation
        this.progressInterval = setInterval(() => {
            this.updateDisplay();
        }, 16);

        // Update text display every 100ms for smooth countdown
        this.timerInterval = setInterval(() => {
            const remaining = this.getRemaining();
            if (this.timerText) {
                this.timerText.textContent =
                    remaining > 0 ? `${Math.ceil(remaining)}s` : "Time's up!";
            }

            if (remaining <= 0) {
                this.stop();
                if (onComplete) onComplete();
            }
        }, 100);
    }

    /**
     * Get remaining time from absolute end time.
     */
    getRemaining() {
        const now = Date.now() / 1000;
        return Math.max(0, this.endTime - now);
    }

    /**
     * Update progress bar display (called from 60fps interval).
     */
    updateDisplay() {
        const remaining = this.getRemaining();
        const totalTime = this.totalTime;

        let percentRemaining = 0;
        if (totalTime > 0) {
            percentRemaining = (remaining / totalTime) * 100;
        }

        if (this.progressBar) {
            this.progressBar.style.width = `${percentRemaining}%`;
            this.progressBar.style.backgroundColor =
                getTimerColor(percentRemaining);
        }
    }

    /**
     * Start timer with local countdown (backward compatible).
     * @param {number} seconds - Seconds to count down
     * @param {function} onComplete - Callback when timer expires
     */
    start(seconds, onComplete = null) {
        this.stop();
        this.remaining = seconds;

        if (this.timerText) {
            this.timerText.textContent = `${this.remaining}s`;
            this.timerText.style.color = '';
        }
        if (this.progressBar) {
            this.progressBar.style.width = '100%';
            this.progressBar.style.backgroundColor = getTimerColor(100);
        }

        const startTime = Date.now();
        const totalMs = seconds * 1000;

        this.progressInterval = setInterval(() => {
            const elapsed = Date.now() - startTime;
            const percentRemaining = Math.max(
                0,
                ((totalMs - elapsed) / totalMs) * 100
            );

            if (this.progressBar) {
                this.progressBar.style.width = `${percentRemaining}%`;
                this.progressBar.style.backgroundColor =
                    getTimerColor(percentRemaining);
            }

            if (percentRemaining <= 0) {
                clearInterval(this.progressInterval);
            }
        }, 50);

        this.timerInterval = setInterval(() => {
            this.remaining--;
            if (this.timerText) {
                this.timerText.textContent = `${this.remaining}s`;
            }

            if (this.remaining <= 0) {
                this.stop();
                if (onComplete) onComplete();
            }
        }, 1000);
    }

    stop() {
        clearInterval(this.timerInterval);
        clearInterval(this.progressInterval);
        this.timerInterval = null;
        this.progressInterval = null;
    }

    setRevealState(text = 'Reveal') {
        this.stop();
        if (this.timerText) {
            this.timerText.textContent = text;
        }
        if (this.progressBar) {
            this.progressBar.style.width = '0%';
            this.progressBar.style.backgroundColor = '#ef4444';
        }
    }
}

/**
 * Countdown overlay manager.
 */
class CountdownOverlay {
    constructor(overlayId, numberId, previewId = null) {
        this.overlay = document.getElementById(overlayId);
        this.numberEl = document.getElementById(numberId);
        this.previewEl = previewId ? document.getElementById(previewId) : null;
        this.interval = null;
    }

    start(questionNum = null, totalQuestions = null) {
        if (this.overlay) this.overlay.classList.remove('hidden');
        if (this.previewEl && questionNum !== null) {
            this.previewEl.textContent =
                `Question ${questionNum} of ${totalQuestions}`;
        }

        let count = 3;
        if (this.numberEl) this.numberEl.textContent = count;

        this.stop();
        this.interval = setInterval(() => {
            count--;
            if (count > 0 && this.numberEl) {
                this.numberEl.textContent = count;
            } else {
                this.stop();
            }
        }, 1000);
    }

    stop() {
        clearInterval(this.interval);
        this.interval = null;
    }

    hide() {
        this.stop();
        if (this.overlay) this.overlay.classList.add('hidden');
    }
}

/**
 * WebSocket connection with automatic reconnection handling.
 */
class QuizWebSocket {
    constructor(url, onMessage, connectionLostId = 'connection-lost') {
        this.url = url;
        this.onMessage = onMessage;
        this.connectionLostEl = document.getElementById(connectionLostId);
        this.ws = null;
        this.isManualClose = false;
        this.reconnectAttempts = 0;
        this.messageQueue = [];
        this.reconnectTimer = null;
        this.connect();
    }

    connect() {
        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                this.hideConnectionLost();
                this.flushMessageQueue();
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.onMessage(data);
            };

            this.ws.onclose = () => {
                console.log('Connection closed');
                if (!this.isManualClose) {
                    this.scheduleReconnect();
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.showConnectionLost();
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.scheduleReconnect();
        }
    }

    scheduleReconnect() {
        if (this.isManualClose) return;

        this.reconnectAttempts++;
        if (this.reconnectAttempts > 10) {
            console.error('Max reconnection attempts reached');
            this.showConnectionLost();
            return;
        }

        // Exponential backoff: min(1000 * 2^(attempts-1), 30000)
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 30000);
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        this.reconnectTimer = setTimeout(() => {
            this.connect();
        }, delay);
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        } else {
            // Queue message if not connected
            this.messageQueue.push(data);
            console.log('Message queued, waiting for connection');
        }
    }

    flushMessageQueue() {
        while (this.messageQueue.length > 0) {
            const data = this.messageQueue.shift();
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify(data));
            }
        }
    }

    showConnectionLost() {
        if (this.connectionLostEl) {
            this.connectionLostEl.classList.remove('hidden');
        }
    }

    hideConnectionLost() {
        if (this.connectionLostEl) {
            this.connectionLostEl.classList.add('hidden');
        }
    }

    close() {
        this.isManualClose = true;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        if (this.ws) {
            this.ws.close();
        }
    }
}

/**
 * Render choice buttons HTML.
 */
function renderChoices(choices, options = {}) {
    const {
        correctIndex = null,
        selectedIndex = null,
        disabled = false,
        onClick = null,
        showUserChoice = false,
    } = options;

    const letters = ['A', 'B', 'C', 'D', 'E', 'F'];

    return choices.map((choice, i) => {
        const classes = ['choice'];

        if (correctIndex !== null) {
            if (i === correctIndex) {
                classes.push('correct');
            } else if (i === selectedIndex) {
                classes.push('wrong');
            } else {
                classes.push('neutral');
            }
        }

        if (showUserChoice && i === selectedIndex) {
            classes.push('user-choice');
        }

        const clickHandler = onClick && !disabled
            ? `onclick="${onClick}(${i})"`
            : '';
        const disabledAttr = disabled ? 'disabled' : '';

        return `
            <button class="${classes.join(' ')}" ${clickHandler} ${disabledAttr}>
                <span class="choice-letter">${letters[i]}</span>
                <span class="choice-text">${renderMarkdown(choice)}</span>
            </button>
        `;
    }).join('');
}
