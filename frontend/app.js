const API_BASE = window.location.origin;

const elements = {
    selectPdfBtn: document.getElementById('selectPdfBtn'),
    selectCsvBtn: document.getElementById('selectCsvBtn'),
    pdfInput: document.getElementById('pdfInput'),
    csvInput: document.getElementById('csvInput'),
    pdfFileName: document.getElementById('pdfFileName'),
    csvFileName: document.getElementById('csvFileName'),
    pdfTypeSelector: document.getElementById('pdfTypeSelector'),
    processBtn: document.getElementById('processBtn'),
    pdfStatus: document.getElementById('pdfStatus'),
    csvStatus: document.getElementById('csvStatus'),
    processStatus: document.getElementById('processStatus'),
    schemaPreview: document.getElementById('schemaPreview'),
    schemaFieldsList: document.getElementById('schemaFieldsList'),
    extractedFields: document.getElementById('extractedFields'),
    fieldsList: document.getElementById('fieldsList'),
    messagesArea: document.getElementById('messagesArea'),
    questionInput: document.getElementById('questionInput'),
    sendBtn: document.getElementById('sendBtn'),
    suggestionsBtn: document.getElementById('suggestionsBtn'),
    suggestionsPanel: document.getElementById('suggestionsPanel'),
    closeSuggestions: document.getElementById('closeSuggestions'),
    leaseTitle: document.getElementById('leaseTitle'),
    clearChatBtn: document.getElementById('clearChatBtn'),
    errorMessage: document.getElementById('errorMessage'),
    navTabs: document.querySelectorAll('.nav-tab'),
    viewSummaryBtn: document.getElementById('viewSummaryBtn'),
    summaryModal: document.getElementById('summaryModal'),
    closeSummaryModal: document.getElementById('closeSummaryModal'),
    summaryContent: document.getElementById('summaryContent'),
    modalTitle: document.getElementById('modalTitle'),
    toggleReportBtn: document.getElementById('toggleReportBtn'),
    downloadCsvBtn: document.getElementById('downloadCsvBtn')
};

let state = {
    pdfUploaded: false,
    csvUploaded: false,
    documentProcessed: false,
    pdfFile: null,
    csvFile: null,
    schemaFields: [],
    markdownSummary: '',
    fullMarkdown: '',
    showingFullReport: false,
    priorityFields: [],
    allFields: [],
    backgroundProcessing: false,
    backgroundComplete: false,
    backgroundPollInterval: null
};

// Configure marked
if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
}

function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        return marked.parse(text);
    }
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

function showError(message) {
    elements.errorMessage.textContent = message;
    elements.errorMessage.style.display = 'block';
    setTimeout(() => elements.errorMessage.style.display = 'none', 8000);
}

function hideError() {
    elements.errorMessage.style.display = 'none';
}

function updateStatusDots() {
    elements.pdfStatus.className = 'status-dot' + (state.pdfUploaded ? ' active' : '');
    elements.csvStatus.className = 'status-dot' + (state.csvUploaded ? ' active' : '');
    elements.processStatus.className = 'status-dot' + (state.documentProcessed ? ' active' : '');
    elements.processBtn.disabled = !state.pdfUploaded;
}

function getSelectedPdfType() {
    const selected = document.querySelector('input[name="pdfType"]:checked');
    return selected ? selected.value : 'text';
}

// PDF Upload
elements.selectPdfBtn.addEventListener('click', () => elements.pdfInput.click());

elements.pdfInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    state.pdfFile = file;
    elements.pdfFileName.textContent = file.name;
    elements.selectPdfBtn.classList.add('uploading');
    elements.selectPdfBtn.querySelector('.btn-text').textContent = 'Uploading...';
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to upload PDF');
        }
        
        state.pdfUploaded = true;
        elements.selectPdfBtn.classList.remove('uploading');
        elements.selectPdfBtn.classList.add('has-file');
        elements.selectPdfBtn.querySelector('.btn-text').textContent = file.name.length > 18 
            ? file.name.substring(0, 15) + '...' 
            : file.name;
        
        elements.pdfTypeSelector.style.display = 'block';
        updateStatusDots();
        hideError();
        
    } catch (error) {
        console.error('Error:', error);
        showError(error.message);
        elements.selectPdfBtn.classList.remove('uploading');
        elements.selectPdfBtn.querySelector('.btn-text').textContent = 'Select PDF Lease';
        state.pdfFile = null;
    }
});

// CSV Upload
elements.selectCsvBtn.addEventListener('click', () => elements.csvInput.click());

elements.csvInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    state.csvFile = file;
    elements.csvFileName.textContent = file.name;
    elements.selectCsvBtn.classList.add('uploading');
    elements.selectCsvBtn.querySelector('.btn-text').textContent = 'Uploading...';
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to upload CSV');
        }
        
        const data = await response.json();
        state.csvUploaded = true;
        state.schemaFields = data.fields || [];
        
        elements.selectCsvBtn.classList.remove('uploading');
        elements.selectCsvBtn.classList.add('has-file');
        elements.selectCsvBtn.querySelector('.btn-text').textContent = `${data.fields_count} fields`;
        
        displaySchemaPreview(state.schemaFields);
        updateStatusDots();
        hideError();
        
    } catch (error) {
        console.error('Error:', error);
        showError(error.message);
        elements.selectCsvBtn.classList.remove('uploading');
        elements.selectCsvBtn.querySelector('.btn-text').textContent = 'Select Schema CSV';
        state.csvFile = null;
    }
});

function displaySchemaPreview(fields) {
    if (!fields || fields.length === 0) {
        elements.schemaPreview.style.display = 'none';
        return;
    }
    
    elements.schemaPreview.style.display = 'block';
    elements.schemaFieldsList.innerHTML = '';
    
    fields.slice(0, 10).forEach(field => {
        const fieldEl = document.createElement('div');
        fieldEl.className = 'schema-field-item';
        fieldEl.innerHTML = `
            <span class="schema-field-name">${field.name}</span>
            <span class="schema-field-type">${field.type}</span>
        `;
        elements.schemaFieldsList.appendChild(fieldEl);
    });
    
    if (fields.length > 10) {
        const moreEl = document.createElement('div');
        moreEl.className = 'schema-field-more';
        moreEl.textContent = `+${fields.length - 10} more fields`;
        elements.schemaFieldsList.appendChild(moreEl);
    }
}

// Start polling for background status
function startBackgroundPolling() {
    if (state.backgroundPollInterval) {
        clearInterval(state.backgroundPollInterval);
    }
    
    state.backgroundPollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/background_status`);
            const data = await response.json();
            
            if (data.complete && !state.backgroundComplete) {
                state.backgroundComplete = true;
                state.backgroundProcessing = false;
                
                // Update full markdown
                if (data.full_markdown) {
                    state.fullMarkdown = data.full_markdown;
                }
                
                // Update toggle button
                elements.toggleReportBtn.querySelector('span').textContent = 'Show Full Report';
                elements.toggleReportBtn.disabled = false;
                
                // Notify user
                addSystemMessage(`Background extraction complete! ${data.fields_with_values}/${data.total_fields} fields extracted. Click "Summary" to view full report.`);
                
                // Refresh extracted fields
                loadLeaseSummary();
                
                // Stop polling
                clearInterval(state.backgroundPollInterval);
                state.backgroundPollInterval = null;
            }
            
            if (data.error) {
                console.error('Background error:', data.error);
                clearInterval(state.backgroundPollInterval);
                state.backgroundPollInterval = null;
            }
            
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 3000); // Poll every 3 seconds
}

// Process Document
elements.processBtn.addEventListener('click', async () => {
    if (!state.pdfUploaded) {
        showError('Please upload a PDF file first');
        return;
    }
    
    hideError();
    
    const pdfType = getSelectedPdfType();
    const originalHtml = elements.processBtn.innerHTML;
    elements.processBtn.disabled = true;
    elements.processBtn.classList.add('processing');
    
    elements.processBtn.innerHTML = `
        <div class="btn-spinner"></div>
        <span class="btn-text">${pdfType === 'scan' ? 'Running OCR...' : 'Processing...'}</span>
    `;
    
    try {
        const formData = new FormData();
        formData.append('pdf_type', pdfType);
        
        const response = await fetch(`${API_BASE}/api/process`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to process document');
        }
        
        const data = await response.json();
        state.documentProcessed = true;
        state.markdownSummary = data.markdown_output || '';
        state.fullMarkdown = data.full_markdown || data.markdown_output || '';
        state.backgroundProcessing = data.background_processing || false;
        state.backgroundComplete = !data.background_processing;
        
        if (data.summary) {
            state.priorityFields = data.summary.priority_fields || [];
            state.allFields = data.summary.fields || [];
        }
        
        elements.processBtn.classList.remove('processing');
        elements.processBtn.classList.add('success');
        elements.processBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            <span class="btn-text">Ready</span>
        `;
        
        // Enable chat immediately
        elements.questionInput.disabled = false;
        elements.sendBtn.disabled = false;
        elements.viewSummaryBtn.style.display = 'flex';
        
        updateStatusDots();
        elements.schemaPreview.style.display = 'none';
        
        // Display priority fields
        if (state.priorityFields && state.priorityFields.length > 0) {
            displayExtractedFields(state.priorityFields);
        }
        
        clearMessages();
        
        // Show summary in chat
        if (state.markdownSummary) {
            addMarkdownMessage(state.markdownSummary, 'assistant');
        }
        
        // Show background processing notice
        if (state.backgroundProcessing) {
            addSystemMessage('Extracting additional fields in background... Chat is ready to use!');
            startBackgroundPolling();
            
            // Disable full report toggle until ready
            elements.toggleReportBtn.querySelector('span').textContent = 'Processing...';
        }
        
        elements.leaseTitle.textContent = 'Ask questions about your lease document';
        
    } catch (error) {
        console.error('Error:', error);
        showError(error.message || 'An error occurred while processing');
        elements.processBtn.disabled = false;
        elements.processBtn.classList.remove('processing');
        elements.processBtn.innerHTML = originalHtml;
    }
});

function displayExtractedFields(fields) {
    elements.extractedFields.style.display = 'flex';
    elements.fieldsList.innerHTML = '';
    
    const fieldsWithValues = fields.filter(f => f.value);
    const fieldsWithoutValues = fields.filter(f => !f.value);
    
    fieldsWithValues.forEach(field => {
        const fieldEl = document.createElement('div');
        fieldEl.className = 'field-item has-value';
        
        const confidenceClass = field.confidence ? field.confidence.toLowerCase() : '';
        const pageRef = field.page_reference ? ` (p.${field.page_reference})` : '';
        
        fieldEl.innerHTML = `
            <div class="field-header">
                <span class="field-name">${field.display_name || field.field_name}</span>
                ${field.confidence ? `<span class="confidence-badge ${confidenceClass}">${field.confidence}</span>` : ''}
            </div>
            <span class="field-value">${field.value}${pageRef}</span>
        `;
        elements.fieldsList.appendChild(fieldEl);
    });
    
    if (fieldsWithoutValues.length > 0) {
        const missingEl = document.createElement('div');
        missingEl.className = 'fields-missing';
        missingEl.textContent = `${fieldsWithoutValues.length} fields not found`;
        elements.fieldsList.appendChild(missingEl);
    }
}

async function sendQuestion(question) {
    if (!question.trim() || !state.documentProcessed) return;
    
    addMessage(question, 'user');
    elements.questionInput.value = '';
    showTypingIndicator();
    
    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        
        if (!response.ok) throw new Error('Failed to get response');
        
        const data = await response.json();
        removeTypingIndicator();
        addMarkdownMessage(data.answer, 'assistant', data.citations);
        
    } catch (error) {
        console.error('Error:', error);
        removeTypingIndicator();
        addMessage('Sorry, there was an error processing your question.', 'assistant');
    }
}

function addMessage(text, sender) {
    const welcomeMsg = elements.messagesArea.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();
    
    const messageGroup = document.createElement('div');
    messageGroup.className = 'message-group';
    
    const messageRow = document.createElement('div');
    messageRow.className = `message-row ${sender === 'user' ? 'mine' : 'theirs'}`;
    
    if (sender === 'assistant') {
        const avatar = document.createElement('div');
        avatar.className = 'avatar assistant';
        avatar.textContent = 'L';
        messageRow.appendChild(avatar);
    }
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = text;
    
    messageRow.appendChild(bubble);
    messageGroup.appendChild(messageRow);
    elements.messagesArea.appendChild(messageGroup);
    scrollToBottom();
}

function addMarkdownMessage(markdown, sender, citations = []) {
    const welcomeMsg = elements.messagesArea.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();
    
    const messageGroup = document.createElement('div');
    messageGroup.className = 'message-group';
    
    const messageRow = document.createElement('div');
    messageRow.className = `message-row ${sender === 'user' ? 'mine' : 'theirs'}`;
    
    if (sender === 'assistant') {
        const avatar = document.createElement('div');
        avatar.className = 'avatar assistant';
        avatar.textContent = 'L';
        messageRow.appendChild(avatar);
    }
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble markdown-content';
    bubble.innerHTML = renderMarkdown(markdown);
    
    if (citations && citations.length > 0) {
        const citationsDiv = document.createElement('div');
        citationsDiv.className = 'citations';
        citationsDiv.innerHTML = `
            <div class="citations-label">Sources</div>
            ${citations.map(c => {
                const pageInfo = c.page_number ? ` (p.${c.page_number})` : '';
                return `<span class="citation-tag" title="${c.text_excerpt || ''}">${c.section_name}${pageInfo}</span>`;
            }).join('')}
        `;
        bubble.appendChild(citationsDiv);
    }
    
    messageRow.appendChild(bubble);
    messageGroup.appendChild(messageRow);
    elements.messagesArea.appendChild(messageGroup);
    scrollToBottom();
}

function addSystemMessage(text) {
    const systemCard = document.createElement('div');
    systemCard.className = 'system-card';
    systemCard.innerHTML = `<span class="label">System</span><span class="value">${text}</span>`;
    elements.messagesArea.appendChild(systemCard);
    scrollToBottom();
}

function showTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'message-group';
    indicator.id = 'typingIndicator';
    indicator.innerHTML = `
        <div class="message-row theirs">
            <div class="avatar assistant">L</div>
            <div class="typing-indicator"><span></span><span></span><span></span></div>
        </div>
    `;
    elements.messagesArea.appendChild(indicator);
    scrollToBottom();
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
}

function clearMessages() {
    elements.messagesArea.innerHTML = '';
}

function scrollToBottom() {
    elements.messagesArea.scrollTop = elements.messagesArea.scrollHeight;
}

function toggleSuggestions() {
    const isVisible = elements.suggestionsPanel.style.display !== 'none';
    elements.suggestionsPanel.style.display = isVisible ? 'none' : 'block';
}

function updateModalContent() {
    const markdown = state.showingFullReport ? state.fullMarkdown : state.markdownSummary;
    elements.summaryContent.innerHTML = renderMarkdown(markdown);
    elements.modalTitle.textContent = state.showingFullReport ? 'Full Extraction Report' : 'Key Lease Terms';
    
    const toggleText = state.showingFullReport ? 'Show Summary' : 'Show Full Report';
    if (state.backgroundComplete || !state.backgroundProcessing) {
        elements.toggleReportBtn.querySelector('span').textContent = toggleText;
    }
}

// Event Listeners
elements.sendBtn.addEventListener('click', () => sendQuestion(elements.questionInput.value));

elements.questionInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendQuestion(elements.questionInput.value);
});

elements.suggestionsBtn.addEventListener('click', toggleSuggestions);
elements.closeSuggestions.addEventListener('click', toggleSuggestions);

document.querySelectorAll('.suggestion-item').forEach(item => {
    item.addEventListener('click', () => {
        elements.questionInput.value = item.textContent;
        toggleSuggestions();
        sendQuestion(item.textContent);
    });
});

elements.clearChatBtn.addEventListener('click', () => {
    if (confirm('Clear chat history?')) {
        clearMessages();
        if (state.documentProcessed) {
            addSystemMessage('Chat cleared. You can continue asking questions.');
        }
    }
});

elements.viewSummaryBtn.addEventListener('click', () => {
    if (state.markdownSummary) {
        state.showingFullReport = false;
        updateModalContent();
        elements.summaryModal.style.display = 'flex';
    }
});

elements.toggleReportBtn.addEventListener('click', () => {
    if (state.backgroundProcessing && !state.backgroundComplete) {
        return; // Don't toggle while processing
    }
    state.showingFullReport = !state.showingFullReport;
    updateModalContent();
});

elements.downloadCsvBtn.addEventListener('click', async () => {
    try {
        const response = await fetch(`${API_BASE}/api/download/csv`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Download failed');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'lease_details.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        console.error('Download error:', error);
        showError(error.message || 'Failed to download CSV');
    }
});

elements.closeSummaryModal.addEventListener('click', () => {
    elements.summaryModal.style.display = 'none';
});

elements.summaryModal.addEventListener('click', (e) => {
    if (e.target === elements.summaryModal) {
        elements.summaryModal.style.display = 'none';
    }
});

elements.navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        elements.navTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
    });
});

async function checkStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        const data = await response.json();
        
        state.pdfUploaded = data.pdf_uploaded;
        state.csvUploaded = data.schema_uploaded;
        state.documentProcessed = data.document_processed;
        state.backgroundProcessing = data.background_processing;
        state.backgroundComplete = data.background_complete;
        
        updateStatusDots();
        
        if (data.pdf_uploaded) {
            elements.selectPdfBtn.classList.add('has-file');
            elements.selectPdfBtn.querySelector('.btn-text').textContent = data.current_file || 'PDF Uploaded';
            elements.pdfTypeSelector.style.display = 'block';
        }
        
        if (data.schema_uploaded) {
            elements.selectCsvBtn.classList.add('has-file');
            elements.selectCsvBtn.querySelector('.btn-text').textContent = `${data.fields_count || 0} fields`;
        }
        
        if (data.document_processed) {
            elements.questionInput.disabled = false;
            elements.sendBtn.disabled = false;
            elements.viewSummaryBtn.style.display = 'flex';
            elements.processBtn.classList.add('success');
            elements.processBtn.innerHTML = `
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
                <span class="btn-text">Ready</span>
            `;
            elements.leaseTitle.textContent = 'Ask questions about your lease document';
            loadLeaseSummary();
            
            // Resume background polling if needed
            if (data.background_processing && !data.background_complete) {
                startBackgroundPolling();
            }
        }
        
    } catch (error) {
        console.log('Checking status...');
    }
}

async function loadLeaseSummary() {
    try {
        const response = await fetch(`${API_BASE}/api/lease_summary`);
        if (!response.ok) return;
        
        const data = await response.json();
        
        state.priorityFields = data.priority_fields || [];
        state.allFields = data.all_fields || [];
        state.markdownSummary = data.markdown || '';
        state.fullMarkdown = data.full_markdown || '';
        state.backgroundComplete = data.background_complete;
        
        // Display priority fields in sidebar
        if (state.priorityFields.length > 0) {
            displayExtractedFields(state.priorityFields);
        }
        
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

checkStatus();
