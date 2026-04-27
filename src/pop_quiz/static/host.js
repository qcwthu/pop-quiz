/**
 * Host Dashboard Logic
 */

const timer = new QuizTimer('progress-bar', 'timer');
const countdown = new CountdownOverlay(
    'countdown-overlay',
    'countdown-number',
    'countdown-preview'
);

let currentPhase = 'lobby';
let currentQuestionIndex = -1;

const quizWs = new QuizWebSocket(
    `ws://${location.host}/ws/host`,
    updateUI
);

document.getElementById('start-btn').onclick = () => {
    quizWs.send({ action: 'start' });
};

document.getElementById('copy-link-btn').onclick = async () => {
    const joinUrl = document.querySelector('.url-text').textContent;
    const btn = document.getElementById('copy-link-btn');
    try {
        await navigator.clipboard.writeText(joinUrl);
        btn.classList.add('copied');
        setTimeout(() => btn.classList.remove('copied'), 1500);
    } catch (err) {
        console.error('Failed to copy:', err);
    }
};

function updateUI(data) {
    document.body.className = `phase-${data.phase}`;

    // Handle countdown phase
    if (data.phase === 'countdown' && currentPhase !== 'countdown') {
        countdown.start(
            data.current_question_index + 1,
            data.total_questions
        );
    } else if (data.phase !== 'countdown' && currentPhase === 'countdown') {
        countdown.hide();
    }

    currentPhase = data.phase;

    updateLobby(data);
    updateLeaderboard(data);
    updateStats(data);
    updateQuestion(data);
    updateFinalResults(data);
}

function updateLobby(data) {
    const participants = data.participants || [];
    const connectedCount = participants.filter(p => p.connected !== false).length;
    document.getElementById('participant-count-text').textContent =
        `${connectedCount} participant${connectedCount !== 1 ? 's' : ''} joined`;
    document.getElementById('start-btn').disabled = connectedCount === 0;

    const waitingCue = document.getElementById('waiting-cue');
    const leaderboardList = document.getElementById('leaderboard-list');

    if (waitingCue) {
        if (connectedCount === 0) {
            waitingCue.classList.remove('hidden');
            if (leaderboardList) leaderboardList.style.display = 'none';
        } else {
            waitingCue.classList.add('hidden');
            if (leaderboardList) leaderboardList.style.display = 'block';
        }
    }
}

function updateStats(data) {
    const participantsEl = document.getElementById('stat-participants');
    const answeredEl = document.getElementById('stat-answered');
    const progressEl = document.getElementById('stat-progress');

    if (!participantsEl || !answeredEl || !progressEl) return;

    // Update participant count
    const participants = data.participants || [];
    const connectedCount = participants.filter(p => p.connected !== false).length;
    participantsEl.textContent = connectedCount;

    // Update answered count
    const answeredCount = data.answers_count || 0;
    answeredEl.textContent = answeredCount;

    // Update progress (current question / total)
    const currentQ = Math.min(data.current_question_index + 1, data.total_questions);
    const totalQ = data.total_questions;
    progressEl.textContent = `${currentQ}/${totalQ}`;
}

function updateLeaderboard(data) {
    const leaderboardList = document.getElementById('leaderboard-list');
    if (!data.participants) {
        leaderboardList.innerHTML = '';
        return;
    }

    const isReveal = data.phase === 'reveal';

    leaderboardList.innerHTML = data.participants.map((p, i) => {
        const answeredClass = p.answered ? 'answered' : '';
        const disconnectedClass = p.connected === false ? 'disconnected' : '';

        let pointsGainedHtml = '';
        if (isReveal && p.points_gained > 0) {
            pointsGainedHtml = `<span class="points-gained">+${p.points_gained}</span>`;
        }

        return `
            <div class="participant ${answeredClass} ${disconnectedClass}">
                <span class="participant-rank">${i + 1}</span>
                <span class="participant-name">${escapeHtml(p.display_name)}</span>
                <span class="participant-score">${p.score}</span>
                ${pointsGainedHtml}
            </div>
        `;
    }).join('');
}

function updateQuestion(data) {
    if (!data.question) return;
    if (data.phase !== 'question' && data.phase !== 'reveal') return;

    document.getElementById('question-number').textContent =
        `Question ${data.current_question_index + 1} of ${data.total_questions}`;
    document.getElementById('question-text').innerHTML =
        renderMarkdown(data.question.text);
    document.getElementById('answers-count').textContent =
        `${data.answers_count} answer${data.answers_count !== 1 ? 's' : ''}`;

    // Handle question image
    const imageContainer = document.getElementById('question-image');
    const imageSrc = document.getElementById('question-image-src');
    if (data.question.image) {
        imageSrc.src = data.question.image;
        imageContainer.style.display = 'block';
    } else {
        imageContainer.style.display = 'none';
    }

    // Start or resume timer when question appears (or after refresh)
    if (data.phase === 'question') {
        const needsTimerStart =
            data.current_question_index !== currentQuestionIndex ||
            (!timer.timerInterval && !timer.progressInterval);

        if (needsTimerStart) {
            currentQuestionIndex = data.current_question_index;
            const timeLimit = data.question.time_limit;
            let timeRemaining = null;

            if (
                data.question.time_remaining !== undefined &&
                data.question.time_remaining !== null
            ) {
                timeRemaining = data.question.time_remaining;
            } else if (
                data.question.question_start_time !== undefined &&
                data.question.question_start_time !== null
            ) {
                const elapsed =
                    Date.now() / 1000 - data.question.question_start_time;
                timeRemaining = Math.max(0, timeLimit - elapsed);
            }

            const serverTime = data.question.server_time ?? null;
            if (timeRemaining !== null && Number.isFinite(timeRemaining)) {
                timer.startSynced(
                    timeRemaining,
                    serverTime,
                    null,
                    timeLimit
                );
            } else {
                timer.start(timeLimit);
            }
        }
    }

    // Update timer display for reveal phase
    if (data.phase === 'reveal') {
        timer.setRevealState('');
    }

    renderChoicesForHost(data);
}

function renderChoicesForHost(data) {
    const letters = ['A', 'B', 'C', 'D', 'E', 'F'];
    const isReveal = data.phase === 'reveal';
    const choicesEl = document.getElementById('choices');

    choicesEl.dataset.count = data.question.choices.length;
    choicesEl.innerHTML = data.question.choices
        .map((choice, i) => {
            const correctClass =
                isReveal && i === data.question.correct ? 'correct' : '';
            return `
                <div class="choice ${correctClass}">
                    <span class="choice-letter">${letters[i]}</span>
                    <span class="choice-text">${renderMarkdown(choice)}</span>
                </div>
            `;
        })
        .join('');
}

function updateFinalResults(data) {
    if (data.phase !== 'finished') return;

    timer.stop();
    document.querySelector('.question-display').style.display = 'none';
    document.querySelector('.final-results').style.display = 'block';

    if (data.participants && data.participants.length > 0) {
        document.getElementById('winner').textContent =
            `Winner: ${escapeHtml(data.participants[0].display_name)}`;

        document.getElementById('final-leaderboard').innerHTML = data
            .participants.slice(0, 5)
            .map(
                (p, i) => `
                <div class="participant">
                    <span class="participant-rank">${i + 1}</span>
                    <span class="participant-name">${escapeHtml(p.display_name)}</span>
                    <span class="participant-score">${p.score}</span>
                </div>
            `
            )
            .join('');
    }
}
