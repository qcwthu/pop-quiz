/**
 * Participant View Logic
 */

// Fullscreen handling
const fullscreenBtn = document.getElementById('fullscreen-btn');

function isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent
    );
}

function isFullscreen() {
    return (
        document.fullscreenElement ||
        document.webkitFullscreenElement ||
        document.mozFullScreenElement
    );
}

function toggleFullscreen() {
    if (isFullscreen()) {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.mozCancelFullScreen) {
            document.mozCancelFullScreen();
        }
    } else {
        const elem = document.documentElement;
        if (elem.requestFullscreen) {
            elem.requestFullscreen();
        } else if (elem.webkitRequestFullscreen) {
            elem.webkitRequestFullscreen();
        } else if (elem.mozRequestFullScreen) {
            elem.mozRequestFullScreen();
        }
    }
}

// Show fullscreen button on mobile devices
if (
    isMobile() &&
    (document.fullscreenEnabled ||
        document.webkitFullscreenEnabled ||
        document.mozFullScreenEnabled)
) {
    fullscreenBtn.classList.remove('hidden');
    fullscreenBtn.addEventListener('click', toggleFullscreen);
}

// Quiz state
const pin = new URLSearchParams(location.search).get('pin');
const storageKey = `pop-quiz-participant-${pin}`;

let participantId = localStorage.getItem(storageKey);
let questionStartTime = null;
let currentQuestionIndex = -1;
let selectedAnswer = null;
let previousScore = 0;
let hasCelebrated = false;

const timer = new QuizTimer('progress-bar', 'timer');
const countdown = new CountdownOverlay(
    'countdown-screen',
    'countdown-number',
    'countdown-question-preview'
);

const quizWs = new QuizWebSocket(
    `ws://${location.host}/ws/participant`,
    handleMessage
);

// Send join message once connected
quizWs.ws.onopen = () => {
    quizWs.send({
        action: 'join',
        pin: pin,
        participant_id: participantId,
    });
};

function handleMessage(data) {
    if (data.error) {
        localStorage.removeItem(storageKey);
        alert(data.error);
        location.href = '/quiz';
        return;
    }

    if (data.joined) {
        participantId = data.participant_id;
        localStorage.setItem(storageKey, participantId);
    }

    updateUI(data);
}

function showScorePopup(points) {
    const popup = document.getElementById('score-popup');
    popup.textContent = `+${points}`;
    popup.classList.remove('hidden');
    setTimeout(() => {
        popup.classList.add('hidden');
    }, 1500);
}

function clearRevealOverlay() {
    const overlay = document.getElementById('reveal-overlay');
    if (!overlay) return;
    overlay.classList.add('hidden');
    overlay.classList.remove('fade-in');
    overlay.classList.remove('fade-out');
    overlay.innerHTML = '';
}

function clearResultHints() {
    const questionEl = document.getElementById('question-screen');
    if (!questionEl) return;
    questionEl.classList.remove(
        'result-correct',
        'result-wrong',
        'result-timeout',
        'shake'
    );
}

function applyResultHint(result) {
    const questionEl = document.getElementById('question-screen');
    if (!questionEl) return;
    questionEl.classList.remove(
        'result-correct',
        'result-wrong',
        'result-timeout'
    );
    if (result) {
        questionEl.classList.add(`result-${result}`);
    }
}

function triggerWrongFeedback() {
    const questionEl = document.getElementById('question-screen');
    if (questionEl) {
        // Remove fade-in to prevent animation restart when shake ends
        questionEl.classList.remove('fade-in');
        
        questionEl.classList.remove('shake');
        void questionEl.offsetWidth;
        questionEl.classList.add('shake');
        setTimeout(() => {
            questionEl.classList.remove('shake');
        }, 500);
    }

    if (navigator.vibrate) {
        navigator.vibrate(120);
    }
}

const confettiColors = [
    '#f97316',
    '#f43f5e',
    '#22c55e',
    '#38bdf8',
    '#eab308',
    '#a855f7',
];

function launchConfetti() {
    const container = document.getElementById('confetti-container');
    if (!container) return;
    container.classList.remove('hidden');
    container.innerHTML = '';

    const pieceCount = 80;
    for (let i = 0; i < pieceCount; i += 1) {
        const piece = document.createElement('span');
        piece.className = 'confetti-piece';

        const size = 6 + Math.random() * 6;
        const drift = (Math.random() - 0.5) * 120;
        const rotation = Math.floor(Math.random() * 360);
        const duration = 2.2 + Math.random() * 1.4;
        const delay = Math.random() * 0.5;

        piece.style.width = `${size}px`;
        piece.style.height = `${size * 0.6}px`;
        piece.style.left = `${Math.random() * 100}%`;
        piece.style.backgroundColor =
            confettiColors[i % confettiColors.length];
        piece.style.setProperty('--rotate', `${rotation}deg`);
        piece.style.setProperty('--drift', `${drift}px`);
        piece.style.animationDuration = `${duration}s`;
        piece.style.animationDelay = `${delay}s`;

        container.appendChild(piece);
    }

    setTimeout(() => {
        container.classList.add('hidden');
        container.innerHTML = '';
    }, 4000);
}

function applyFadeIn(el) {
    if (!el) return;
    el.classList.remove('fade-in');
    void el.offsetWidth;
    el.classList.add('fade-in');
}

function normalizeRevealBadges(overlay) {
    if (!overlay) return;
    const optionalBadge = overlay.querySelector('.reveal-badge.optional');
    if (!optionalBadge) return;

    optionalBadge.classList.remove('hidden');
    optionalBadge.classList.remove('compact');
    overlay.classList.remove('tight');
    if (optionalBadge.dataset.fullText) {
        optionalBadge.textContent = optionalBadge.dataset.fullText;
    }

    if (overlay.scrollWidth > overlay.clientWidth) {
        const shortText = optionalBadge.dataset.shortText;
        if (shortText) {
            optionalBadge.textContent = shortText;
            optionalBadge.classList.add('compact');
        }
    }

    if (overlay.scrollWidth > overlay.clientWidth) {
        overlay.classList.add('tight');
    }
}

function showScreen(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('hidden');
    applyFadeIn(el);
}

let choiceLayoutFrame = null;
let choiceResizeTimer = null;

function applyChoiceLayout() {
    const choicesEl = document.getElementById('choices');
    if (!choicesEl) return;

    const choiceEls = Array.from(choicesEl.querySelectorAll('.choice'));
    if (!choiceEls.length) return;

    const isCompact = window.matchMedia('(max-width: 540px)').matches;

    choiceEls.forEach((choice) => choice.classList.remove('choice-wide'));

    if (!isCompact) return;

    const candidates = choiceEls
        .map((choice) => {
            const textEl = choice.querySelector('.choice-text');
            if (!textEl) return null;

            const styles = window.getComputedStyle(textEl);
            const lineHeight = parseFloat(styles.lineHeight);
            const fontSize = parseFloat(styles.fontSize) || 16;
            const effectiveLineHeight = Number.isNaN(lineHeight)
                ? fontSize * 1.4
                : lineHeight;
            if (!effectiveLineHeight) return null;

            const lineCount = Math.round(
                textEl.scrollHeight / effectiveLineHeight
            );
            return { choice, lineCount };
        })
        .filter((item) => item && item.lineCount >= 3);

    candidates
        .sort((a, b) => b.lineCount - a.lineCount)
        .slice(0, 2)
        .forEach((item) => item.choice.classList.add('choice-wide'));
}

function scheduleChoiceLayout() {
    if (choiceLayoutFrame) return;
    choiceLayoutFrame = window.requestAnimationFrame(() => {
        choiceLayoutFrame = null;
        applyChoiceLayout();
    });
}

window.addEventListener('resize', () => {
    if (choiceResizeTimer) {
        clearTimeout(choiceResizeTimer);
    }
    choiceResizeTimer = setTimeout(() => {
        applyChoiceLayout();
        normalizeRevealBadges(document.getElementById('reveal-overlay'));
    }, 150);
});

function updateUI(data) {
    // Clear any existing progress bar mirror interval
    if (window.answerMirrorInterval) {
        clearInterval(window.answerMirrorInterval);
        window.answerMirrorInterval = null;
    }

    if (data.phase === 'lobby') {
        hasCelebrated = false;
    }

    document.getElementById('display-name').textContent =
        data.display_name || 'Joining...';

    // Check for score increase and show animation
    const newScore = data.score || 0;
    if (newScore > previousScore && previousScore > 0) {
        showScorePopup(newScore - previousScore);
    }
    previousScore = newScore;
    document.getElementById('score').textContent = newScore;

    // Hide all screens
    const screens = [
        'waiting-screen',
        'countdown-screen',
        'question-screen',
        'answered-screen',
        'results-screen',
    ];
    screens.forEach((id) => document.getElementById(id).classList.add('hidden'));
    clearRevealOverlay();
    clearResultHints();
    const timerEl = document.getElementById('timer');
    if (timerEl) {
        timerEl.classList.remove('overlay-hidden');
    }

    switch (data.phase) {
        case 'lobby':
            showScreen('waiting-screen');
            break;
        case 'countdown':
            showCountdown(data);
            break;
        case 'question':
            if (data.has_answered) {
                showScreen('answered-screen');

                // Mirror progress bar updates from question-screen to answered-screen
                const sourceBar = document.getElementById('progress-bar');
                const targetBar = document.getElementById('answered-progress-bar');
                const targetText = document.getElementById('answered-timer');

                // Initial sync
                if (sourceBar && targetBar) {
                    targetBar.style.width = sourceBar.style.width;
                    targetBar.style.backgroundColor = sourceBar.style.backgroundColor;
                }
                if (timer.timerText && targetText) {
                    targetText.textContent = timer.timerText.textContent;
                }

                // Continuous sync
                window.answerMirrorInterval = setInterval(() => {
                    if (sourceBar && targetBar) {
                        targetBar.style.width = sourceBar.style.width;
                        targetBar.style.backgroundColor = sourceBar.style.backgroundColor;
                    }
                    if (timer.timerText && targetText) {
                        targetText.textContent = timer.timerText.textContent;
                    }
                }, 50);
            } else {
                showQuestion(data);
            }
            break;
        case 'reveal':
            showReveal(data);
            break;
        case 'finished':
            showResults(data);
            break;
    }
}

function showCountdown(data) {
    showScreen('countdown-screen');
    countdown.start(data.current_question_index + 1, data.total_questions);
    updateCountdownLeaderboard(data);
}

function updateCountdownLeaderboard(data) {
    const container = document.getElementById('countdown-leaderboard');
    const listEl = document.getElementById('countdown-leaderboard-list');
    if (!container || !listEl) return;

    if (!data.leaderboard || data.leaderboard.length === 0) {
        container.classList.add('hidden');
        listEl.innerHTML = '';
        return;
    }

    listEl.innerHTML = data.leaderboard
        .map((entry, index) => {
            const classes = ['participant'];
            if (entry.is_self) {
                classes.push('is-self');
            }
            const tag = entry.is_self
                ? '<span class="participant-tag">You</span>'
                : '';
            return `
                <div class="${classes.join(' ')}">
                    <span class="participant-rank">${index + 1}</span>
                    <span class="participant-name">${escapeHtml(entry.display_name)}</span>
                    ${tag}
                    <span class="participant-score">${entry.score}</span>
                </div>
            `;
        })
        .join('');
    container.classList.remove('hidden');
}

function showQuestion(data) {
    showScreen('question-screen');
    clearRevealOverlay();
    const timerEl = document.getElementById('timer');
    if (timerEl) {
        timerEl.classList.remove('overlay-hidden');
    }

    if (data.current_question_index !== currentQuestionIndex) {
        currentQuestionIndex = data.current_question_index;
        questionStartTime = Date.now();
        selectedAnswer = null;

        // Use server-synced timer if available, otherwise fall back to local timer
        if (data.question.time_remaining !== undefined && data.question.server_time !== undefined) {
            const timeRemaining = data.question.time_remaining ?? data.question.time_limit;
            const serverTime = data.question.server_time;

            timer.startSynced(
                timeRemaining,
                serverTime,
                () => {
                    document.getElementById('timer').textContent = "Time's up!";
                    document.querySelectorAll('.choice').forEach((btn) => {
                        btn.disabled = true;
                        btn.classList.add('timeout');
                    });
                },
                data.question.time_limit
            );
        } else {
            timer.start(data.question.time_limit, () => {
                document.getElementById('timer').textContent = "Time's up!";
                document.querySelectorAll('.choice').forEach((btn) => {
                    btn.disabled = true;
                    btn.classList.add('timeout');
                });
            });
        }
    }

    document.getElementById('question-number').textContent =
        `Question ${data.current_question_index + 1} of ${data.total_questions}`;

    // Handle image
    const imageEl = document.getElementById('question-image');
    if (data.question.image) {
        imageEl.src = data.question.image;
        imageEl.classList.remove('hidden');
    } else {
        imageEl.classList.add('hidden');
    }

    document.getElementById('question-text').innerHTML = renderMarkdown(
        data.question.text
    );

    const letters = ['A', 'B', 'C', 'D', 'E', 'F'];
    const choicesEl = document.getElementById('choices');
    choicesEl.dataset.count = data.question.choices.length;
    choicesEl.innerHTML = data.question.choices
        .map(
            (choice, i) => `
            <button class="choice" onclick="submitAnswer(${i})">
                <span class="choice-letter">${letters[i]}</span>
                <span class="choice-text">${renderMarkdown(choice)}</span>
            </button>
        `
        )
        .join('');
    scheduleChoiceLayout();
}

function showReveal(data) {
    showScreen('question-screen');
    timer.stop();

    document.getElementById('question-number').textContent =
        `Question ${data.current_question_index + 1} of ${data.total_questions}`;
    document.getElementById('question-text').innerHTML = renderMarkdown(
        data.question.text
    );

    // Show result based on whether user answered correctly
    const timerEl = document.getElementById('timer');
    if (timerEl) {
        timerEl.classList.add('overlay-hidden');
    }
    document.getElementById('progress-bar').style.width = '0%';

    const correctIndex = data.question.correct;
    const selectedIndex = data.question.selected;
    const timeTaken = data.question.time_taken;
    const pointsGained = data.question.points_gained;

    // Build result display with stats
    let resultText = '';
    let resultClass = '';

    if (selectedIndex !== null && selectedIndex !== undefined) {
        if (selectedIndex === correctIndex) {
            resultText = 'Correct!';
            resultClass = 'correct';
            applyResultHint('correct');
        } else {
            resultText = 'Wrong!';
            resultClass = 'wrong';
            applyResultHint('wrong');
            triggerWrongFeedback();
        }
    } else {
        resultText = "Time's up!";
        resultClass = 'timeout';
        applyResultHint('timeout');
    }

    const overlay = document.getElementById('reveal-overlay');
    if (overlay) {
        let statsHtml = `<div class="reveal-badge result ${resultClass}">${resultText}</div>`;
        if (timeTaken !== null && timeTaken !== undefined) {
            const fullTimeText = `Answered in ${timeTaken.toFixed(1)}s`;
            const shortTimeText = `${timeTaken.toFixed(1)}s`;
            statsHtml += `
                <div class="reveal-badge optional"
                    data-full-text="${fullTimeText}"
                    data-short-text="${shortTimeText}">
                    ${fullTimeText}
                </div>
            `;
        }
        if (pointsGained !== null && pointsGained !== undefined) {
            const pointsLabel = pointsGained >= 0
                ? `+${pointsGained}`
                : `${pointsGained}`;
            const pointsClasses = ['reveal-badge', 'points'];
            if (pointsGained > 0) {
                pointsClasses.push('positive');
            } else if (pointsGained < 0) {
                pointsClasses.push('negative');
            }
            statsHtml += `<div class="${pointsClasses.join(' ')}">${pointsLabel}</div>`;
        }
        overlay.innerHTML = statsHtml;
        overlay.classList.remove('hidden');
        applyFadeIn(overlay);
        window.requestAnimationFrame(() => {
            normalizeRevealBadges(overlay);
        });
    }

    // Handle image
    const imageEl = document.getElementById('question-image');
    if (data.question.image) {
        imageEl.src = data.question.image;
        imageEl.classList.remove('hidden');
    } else {
        imageEl.classList.add('hidden');
    }

    const letters = ['A', 'B', 'C', 'D', 'E', 'F'];
    const choicesEl = document.getElementById('choices');
    choicesEl.dataset.count = data.question.choices.length;
    choicesEl.innerHTML = data.question.choices
        .map((choice, i) => {
            let colorClass = 'neutral';
            if (i === correctIndex) {
                colorClass = 'correct';
            } else if (i === selectedIndex) {
                colorClass = 'wrong';
            }
            const userChoiceClass = i === selectedIndex ? 'user-choice' : '';
            const yourChoiceBadge = i === selectedIndex
                ? '<span class="choice-indicator-label" aria-label="Your choice">Your choice</span>'
                : '';
            return `
                <button class="choice ${colorClass} ${userChoiceClass}" disabled>
                    <span class="choice-letter">${letters[i]}</span>
                    <span class="choice-text">${renderMarkdown(choice)}</span>
                    ${yourChoiceBadge}
                </button>
            `;
        })
        .join('');
    scheduleChoiceLayout();
}

function showResults(data) {
    showScreen('results-screen');
    document.getElementById('final-score').textContent = data.score || 0;
    document.getElementById('results-title').textContent = 'Quiz Complete!';

    if (data.leaderboard) {
        const total = data.total_participants || data.leaderboard.length;
        let resolvedRank = data.rank || null;
        if (!resolvedRank && data.display_name) {
            const fallbackRank =
                data.leaderboard.findIndex(
                    (p) => p.display_name === data.display_name
                ) + 1;
            resolvedRank = fallbackRank > 0 ? fallbackRank : null;
        }

        if (resolvedRank === 1) {
            document.getElementById('results-title').textContent = 'You won!';
            document.getElementById('rank').textContent = '';
        } else {
            const rankText = resolvedRank
                ? `Rank: #${resolvedRank} / ${total}`
                : '';
            document.getElementById('rank').textContent = rankText;
        }

        document.getElementById('final-leaderboard').innerHTML = data.leaderboard
            .map(
                (p, i) => `
                <div class="leaderboard-item">
                    <span>${i + 1}. ${p.display_name}</span>
                    <span>${p.score}</span>
                </div>
            `
            )
            .join('');
    }

    if (data.rank === 1 && !hasCelebrated) {
        hasCelebrated = true;
        launchConfetti();
    }

    // Setup question review
    if (data.all_questions) {
        setupQuestionReview(data);
    }
}

function setupQuestionReview(data) {
    const reviewEl = document.getElementById('review-questions');
    const letters = ['A', 'B', 'C', 'D', 'E', 'F'];

    reviewEl.innerHTML = data.all_questions
        .map((q, qIndex) => {
            const imageHtml = q.image
                ? `<img class="review-question-image" src="${q.image}" alt="Question image">`
                : '';

            // Determine status
            let statusClass, statusText;
            const answered = q.selected !== null && q.selected !== undefined;
            if (!answered) {
                statusClass = 'timeout';
                statusText = 'Timed Out';
            } else if (q.selected === q.correct) {
                statusClass = 'correct';
                statusText = 'Correct';
            } else {
                statusClass = 'wrong';
                statusText = 'Wrong';
            }

            // Build stats display
            const timeHtml = q.time_taken !== null && q.time_taken !== undefined
                ? `<span class="review-time">${q.time_taken.toFixed(1)}s</span>`
                : '';
            const pointsHtml = q.points_gained !== null && q.points_gained !== undefined
                ? `<span class="review-points ${q.points_gained > 0 ? 'positive' : ''}">+${q.points_gained} pts</span>`
                : '';

            const choicesHtml = q.choices
                .map((choice, i) => {
                    let colorClass = 'neutral';
                    if (i === q.correct) colorClass = 'correct';
                    else if (i === q.selected && q.selected !== q.correct)
                        colorClass = 'wrong';

                    let marker = '';
                    if (i === q.correct) marker = ' ✓';
                    else if (i === q.selected) marker = ' ✗';

                    return `<div class="review-choice ${colorClass}">${letters[i]}. ${renderMarkdown(choice)}${marker}</div>`;
                })
                .join('');

            return `
                <div class="review-question">
                    <div class="review-question-header">
                        <span class="review-question-number">${qIndex + 1}. ${renderMarkdown(q.text)}</span>
                        <div class="review-question-stats">
                            <span class="review-status ${statusClass}">${statusText}</span>
                            ${timeHtml}
                            ${pointsHtml}
                        </div>
                    </div>
                    ${imageHtml}
                    ${choicesHtml}
                </div>
            `;
        })
        .join('');

    document.getElementById('review-toggle').onclick = () => {
        reviewEl.classList.toggle('hidden');
        document.getElementById('review-toggle').textContent =
            reviewEl.classList.contains('hidden')
                ? 'Review Answers'
                : 'Hide Review';
    };
}

function submitAnswer(choice) {
    // Check if timer has expired (works with both synced and local timers)
    const timeRemaining = timer.endTime > 0 ? timer.getRemaining() : timer.remaining;
    if (timeRemaining <= 0) return;

    const timeTaken = (Date.now() - questionStartTime) / 1000;
    selectedAnswer = choice;

    quizWs.send({
        action: 'answer',
        question_index: currentQuestionIndex,
        choice: choice,
        time_taken: timeTaken,
    });

    document.querySelectorAll('.choice').forEach((btn, i) => {
        btn.disabled = true;
        if (i === choice) btn.classList.add('selected');
    });
}

// Handle visibility changes (app switch, tab switch)
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        // Page became visible, attempt to reconnect if disconnected
        if (quizWs.ws.readyState !== WebSocket.OPEN) {
            console.log('Reconnecting after visibility change');
            quizWs.connect();
        }
    }
});

// Handle online/offline events
window.addEventListener('online', () => {
    console.log('Network connectivity restored');
    if (quizWs.ws.readyState !== WebSocket.OPEN) {
        quizWs.connect();
    }
});

window.addEventListener('offline', () => {
    console.log('Network connectivity lost');
    quizWs.showConnectionLost();
});
