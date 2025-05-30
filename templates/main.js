
// UX/UI functionality for the tools browser interface

function showTab(tabId, evt) {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');});
    document.querySelectorAll('.tab-buttons button').forEach(btn => {
        btn.classList.remove('active');});
    document.getElementById(tabId).classList.add('active');
    evt.target.classList.add('active');
}

let selectedTable = null;

document.getElementById('fileInput').addEventListener('change', async function(e) {
    const file = e.target.files[0];
    const tableSelection = document.getElementById('tableSelection');
    tableSelection.style.display = 'none';
    selectedTable = null;
    
    if (!file) {
        document.getElementById('previewData').textContent = 'Select an input file to see preview';
        return;
    }

    const extension = file.name.toLowerCase().split('.').pop();
    const supportedFormats = ['csv', 'json', 'sqlite', 'xml'];
    
    if (!supportedFormats.includes(extension)) {
        alert('Unsupported file format. Please select a CSV, JSON, SQLite, or XML file.');
        this.value = '';
        return;
    }

    if (extension === 'sqlite') {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('output_format', 'sqlite');

        try {
            const response = await fetch('/convert', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const jsonData = await response.json();
                if (jsonData.type === 'tables') {
                    const select = document.getElementById('tableSelect');
                    select.innerHTML = jsonData.tables
                        .map(t => `<option value="${t}">${t}</option>`).join('');
                    document.getElementById('tableSelectionMessage').textContent = 
                        'Hold Ctrl/Cmd to select multiple tables';
                    tableSelection.style.display = 'block';
                    
                    // select first table by default
                    if (jsonData.tables.length > 0) {
                        select.options[0].selected = true;
                        // trigger preview update for the selected table
                        setTimeout(() => updatePreview(), 0);
                    }
                }
            }
        } catch (error) {
            console.error('Error fetching tables:', error);
        }
    } else {
        // for non-SQLite files, update preview directly
        updatePreview();
    }
});

// event listener for output format changes
document.getElementById('outputFormat').addEventListener('change', function() {
    updatePreview();
});

// event listener for table selection changes
document.getElementById('tableSelect').addEventListener('change', function() {
    updatePreview();
});

function selectAllTables() {
    const options = document.getElementById('tableSelect').options;
    for (let i = 0; i < options.length; i++) {
        options[i].selected = true;
    }
    updatePreview();
}

function deselectAllTables() {
    const options = document.getElementById('tableSelect').options;
    for (let i = 0; i < options.length; i++) {
        options[i].selected = false;
    }
    // no preview update as no table is selected
    document.getElementById('previewContainer').style.display = 'none';
}

async function updatePreview() {
    const fileInput = document.getElementById('fileInput');
    const outputFormat = document.getElementById('outputFormat').value;
    const file = fileInput.files[0];
    
    if (!file) {
        return;
    }

    const previewData = document.getElementById('previewData');
    previewData.textContent = 'Loading preview...';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('output_format', outputFormat);
    // Always apply flattening for previews to avoid unnecessary warnings
    formData.append('flatten', 'true');

    // add any selected table for SQLite files
    const tableSelect = document.getElementById('tableSelect');
    if (tableSelect.style.display !== 'none' && tableSelect.value) {
        formData.append('table', tableSelect.value);
    }

    try {
        const response = await fetch('/preview', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        const result = await response.json();
        
        if (result.type === 'preview') {
            displayPreview(result);
        }
        // Remove the semi_data_warning handling for preview
    } catch (error) {
        previewData.textContent = 'Error: ' + error.message;
    }
}

function displayPreview(result) {
    previewData.tempPath = result.temp_path;
    previewData.format = document.getElementById('outputFormat').value;
    
    const previewContainer = document.getElementById('previewContainer');
    const previewDataElement = document.getElementById('previewData');
    previewContainer.style.display = 'block';
    
    previewDataElement.className = `preview-data ${previewData.format}-view`;
    
    if (previewData.format === 'sqlite') {
        previewDataElement.innerHTML = result.data;  // use HTML for grid view
    } else {
        previewDataElement.textContent = result.data;  // use text for other formats
    }
}

async function handleConversion(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('fileInput');
    const outputFormat = document.getElementById('outputFormat').value;
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a file');
        return;
    }

    // show loading state
    const button = e.target;
    const originalText = button.textContent;
    button.textContent = 'Converting...';
    button.disabled = true;

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('output_format', outputFormat);
        
        // add table selection if SQLite
        const tableSelect = document.getElementById('tableSelect');
        if (tableSelect.style.display !== 'none') {
            const selectedOptions = Array.from(tableSelect.selectedOptions);
            if (selectedOptions.length > 0) {
                if (selectedOptions.length === 1) {
                    formData.append('table', selectedOptions[0].value);
                } else {
                    formData.append('table', '*');
                }
            }
        }

        // first check if data requires flattening
        const checkResponse = await fetch('/check-structure', {
            method: 'POST',
            body: formData
        });

        if (!checkResponse.ok) {
            throw new Error(await checkResponse.text());
        }

        const checkResult = await checkResponse.json();
        
        let shouldFlatten = false;
        let shouldContinue = true;  // flag to determine whether to continue with conversion
        
        if (checkResult.type === 'semi_data_warning') {
            // ask user about flattening before showing file dialog
            if (confirm(checkResult.message)) {
                shouldFlatten = true;
            } else {
                // user declined to flatten, don't continue with conversion
                shouldContinue = false;
            }
        }
        
        // only continue with the conversion if we don't need flattening or user agreed to flatten
        if (shouldContinue) {
            if (shouldFlatten) {
                formData.append('flatten', 'true');
            }

            // proceed with conversion
            const response = await fetch('/convert', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const result = await response.json();
            if (result.type === 'success') {
                alert('Conversion completed successfully!');
            }
        } else {
            // inform the user if the conversion was cancelled
            alert('Conversion cancelled.');
        }
    } catch (error) {
        console.error('Conversion error:', error);
        alert('Error during conversion: ' + error.message);
    } finally {
        button.disabled = false;
        button.textContent = originalText;
    }
}

let previewData = {
    tempPath: null,
    format: null
};

function showPreview(result) {
    previewData.tempPath = result.temp_path;
    previewData.format = document.getElementById('outputFormat').value;
    
    const previewContainer = document.getElementById('previewData');
    previewContainer.className = `preview-data ${previewData.format}-view`;
    
    if (previewData.format === 'sqlite') {
        previewContainer.innerHTML = result.data;  // use HTML for grid view
    } else {
        previewContainer.textContent = result.data;  // use text for other formats
    }
}

async function getSaveFilePath(title, defaultName) {
    const response = await fetch('/save-dialog', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            title: title,
            default_name: defaultName
        })
    });
    
    if (!response.ok) {
        throw new Error('Failed to get save path');
    }
    
    const result = await response.json();
    return result.path;
}

async function handleGeneration() {
    const form = document.getElementById('generateForm');
    const rows = parseInt(form.querySelector('[name="rows"]').value);
    const format = form.querySelector('[name="format"]').value;
    const configSelect = document.getElementById('configSelect');
    const selectedConfig = configSelect.value;

    if (isNaN(rows) || rows < 1) {
        alert('Invalid row count');
        return;
    }

    if (selectedConfig === 'new' || !selectedConfig) {
        alert('Please save your configuration before generating data');
        return;
    }

    const button = document.querySelector('#generateForm button[type="button"]');
    button.disabled = true;
    button.textContent = 'Generating...';

    try {
        const response = await fetch('/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                rows: rows,
                format: format,
                config: selectedConfig
            })
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        const result = await response.json();
        if (result.type === 'success') {
            alert(result.message);
        } else if (result.type === 'cancelled') {
            console.log('Operation cancelled');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    } finally {
        button.disabled = false;
        button.textContent = 'Generate';
    }
}

// event listeners
document.addEventListener('DOMContentLoaded', function() {
    loadConfigs();
});

// new config creation
function newConfig() {
    currentConfig = {
        headers: [],
        patterns: {}
    };
    
    document.getElementById('configNameInput').value = 'new_config.json';
    document.getElementById('patternRows').innerHTML = '';
    
    // show the pattern builder modal
    const patternBuilderModal = document.getElementById('patternBuilderModal');
    patternBuilderModal.style.display = 'block';
    
    setTimeout(() => {
        makeDraggable(patternBuilderModal);
    }, 0);
}

// edit existing config
async function editConfig() {
    const configSelect = document.getElementById('configSelect');
    const selectedConfig = configSelect.value;
    
    if (!selectedConfig) {
        alert('Please select a configuration to edit');
        return;
    }
    
    try {
        const response = await fetch('/get-config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                config: selectedConfig
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to load configuration');
        }
        
        const result = await response.json();
        currentConfig = result.config;
        
        document.getElementById('configNameInput').value = selectedConfig;
        
        const patternBuilderModal = document.getElementById('patternBuilderModal');
        patternBuilderModal.style.display = 'block';
        
        // render rows and make draggable AFTER the modal is displayed
        setTimeout(() => {
            renderPatternRows();
            makeDraggable(patternBuilderModal);
        }, 0);
    } catch (error) {
        console.error('Error editing config:', error);
        alert('Failed to edit configuration: ' + error.message);
    }
}

function editPattern(field) {
    currentEditField = field;
    
    const pattern = currentConfig.patterns[field] || '';
    
    // parse the pattern into tokens and render them
    currentTokens = tokenizePattern(pattern);
    renderTokens(currentTokens);
    
    // clear previous preview samples
    document.getElementById('previewSamples').innerHTML = '';
    
    // show the pattern edit modal
    document.getElementById('patternEditModal').style.display = 'block';
    
    // test the pattern immediately
    testPattern();
}

function deletePattern(field) {
    if (confirm(`Are you sure you want to delete the field "${field}"?`)) {
        const index = currentConfig.headers.indexOf(field);
        if (index !== -1) {
            currentConfig.headers.splice(index, 1);
            delete currentConfig.patterns[field];
            renderPatternRows();
        }
    }
}

// function for adding a one of the supported rules to the pattern
function addToPattern(component) {
    const tokens = tokenizePattern(component);
    const editableTokens = ['[a-z]', '[A-Z]', '[0-9]', '{3}', '{1,5}', '(a|b)', 'abc'];
    
    // add the token(s) to the current token list
    const startIdx = currentTokens.length;
    currentTokens = [...currentTokens, ...tokens];
    renderTokens(currentTokens);
    
    // if this is an editable token type, trigger edit mode immediately
    if (editableTokens.includes(component)) {
        setTimeout(() => {
            // for tokens that produce only one token (most components)
            if (tokens.length === 1) {
                const newTokenIndex = startIdx;
                const tokenElem = document.querySelector(`.pattern-token[data-index="${newTokenIndex}"]`);
                if (tokenElem) {
                    tokenElem.click(); // trigger edit mode
                }
            }
            // for components that might produce multiple tokens (rare)
            else if (tokens.length > 1) {
                // just focus the first one
                const newTokenIndex = startIdx;
                const tokenElem = document.querySelector(`.pattern-token[data-index="${newTokenIndex}"]`);
                if (tokenElem) {
                    tokenElem.click(); // trigger edit mode
                }
            }
        }, 0);
    } else {
        testPattern();
    }
}

// remove a token by index
function removeToken(index) {
    currentTokens.splice(index, 1);
    renderTokens(currentTokens);
    testPattern();
}

// drag and drop functionality for changing token order
let draggedToken = null;

function handleDragStart(e) {
    if (this.classList.contains('editing')) {
        e.preventDefault();
        return false;
    }
    
    this.classList.add('dragging');
    draggedToken = this;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', this.getAttribute('data-index'));
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDrop(e) {
    e.preventDefault();
    const sourceIndex = parseInt(e.dataTransfer.getData('text/plain'));
    const targetIndex = parseInt(this.getAttribute('data-index'));
    
    if (sourceIndex !== targetIndex) {
        // reorder tokens
        const temp = currentTokens[sourceIndex];
        currentTokens.splice(sourceIndex, 1);
        currentTokens.splice(targetIndex, 0, temp);
        renderTokens(currentTokens);
        // update preview after reordering
        testPattern(); 
    }
    return false;
}

function handleDragEnd() {
    document.querySelectorAll('.pattern-token').forEach(item => {
        item.classList.remove('dragging');
    });
    draggedToken = null;
}

// render tokens in the editor
function renderTokens(tokens) {
    const container = document.getElementById('tokenContainer');
    container.innerHTML = '';
    
    tokens.forEach((token, index) => {
        const tokenElem = document.createElement('div');
        tokenElem.className = `pattern-token ${token.type}`;
        tokenElem.setAttribute('data-index', index);
        tokenElem.setAttribute('draggable', true);
        
        // content span
        const contentSpan = document.createElement('span');
        contentSpan.className = 'pattern-token-content';
        contentSpan.textContent = token.display;
        tokenElem.appendChild(contentSpan);
        
        // editable input
        const editInput = document.createElement('input');
        editInput.type = 'text';
        editInput.className = 'pattern-token-edit';
        editInput.value = token.display;
        tokenElem.appendChild(editInput);
        
        // delete button
        const deleteBtn = document.createElement('span');
        deleteBtn.className = 'token-delete';
        deleteBtn.innerHTML = '&times;';
        deleteBtn.onclick = (e) => {
            // prevent token click when delete is clicked
            e.stopPropagation(); 
            removeToken(index);
        };
        tokenElem.appendChild(deleteBtn);
        
        // setup click to edit
        tokenElem.addEventListener('click', function(e) {
            if (!this.classList.contains('editing')) {
                // enable editing
                this.classList.add('editing');
                
                const input = this.querySelector('.pattern-token-edit');
                input.focus();
                input.select();
                
                // input event handler to adjust width as user types into the field
                input.addEventListener('input', function() {
                    // hidden span to measure text width
                    const tempSpan = document.createElement('span');
                    tempSpan.style.font = window.getComputedStyle(input).font;
                    tempSpan.style.position = 'absolute';
                    tempSpan.style.visibility = 'hidden';
                    tempSpan.style.whiteSpace = 'pre';
                    tempSpan.textContent = this.value || this.placeholder || '';
                    
                    document.body.appendChild(tempSpan);
                    const calculatedWidth = tempSpan.getBoundingClientRect().width + 20;
                    document.body.removeChild(tempSpan);
                    
                    // set width (with minimum)
                    this.style.width = Math.max(40, calculatedWidth) + 'px';
                });
                
                // trigger input event to set initial width
                input.dispatchEvent(new Event('input'));
                
                // stop drag during edit
                this.setAttribute('draggable', 'false');
            }
        });
        
        // setup edit field events
        editInput.addEventListener('blur', function() {
            saveTokenEdit(index, this.value);
        });
        
        editInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveTokenEdit(index, this.value);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancelTokenEdit(index);
            }
        });
        
        // drag events
        tokenElem.addEventListener('dragstart', handleDragStart);
        tokenElem.addEventListener('dragover', handleDragOver);
        tokenElem.addEventListener('drop', handleDrop);
        tokenElem.addEventListener('dragend', handleDragEnd);
        
        container.appendChild(tokenElem);
    });
    
    // update hidden input with pattern
    document.getElementById('patternInput').value = tokensToPattern(tokens);
}

// save token edit - updated to update preview after editing
function saveTokenEdit(index, newValue) {
    const token = currentTokens[index];
    if (newValue.trim() && newValue !== token.display) {
        // try to parse the new value into appropriate token type
        try {
            // for special token types, maintain their type but update display/value
            if (token.type === 'character-class' || 
                token.type === 'quantifier' || 
                token.type === 'escape' || 
                token.type === 'alternation') {
                
                const oldType = token.type;
                
                // validate the format based on token type
                if (oldType === 'character-class' && !isValidCharacterClass(newValue)) {
                    throw new Error('Invalid character class format');
                } else if (oldType === 'quantifier' && !isValidQuantifier(newValue)) {
                    throw new Error('Invalid quantifier format');
                } else if (oldType === 'alternation' && !isValidAlternation(newValue)) {
                    throw new Error('Invalid alternation format');
                }
                
                token.display = newValue;
                token.value = newValue;
            } else {
                // for literals and other simple types, just update
                token.display = newValue;
                token.value = newValue;
            }
            
            renderTokens(currentTokens);
            testPattern(); // update preview after editing
        } catch (e) {
            alert('Invalid token format: ' + e.message);
            cancelTokenEdit(index);
        }
    } else {
        cancelTokenEdit(index);
    }
}

// cancel token edit
function cancelTokenEdit(index) {
    renderTokens(currentTokens);
    testPattern(); // just in case the pattern was changed, update preview
}

// validate character class format like [a-z], [0-9], etc.
function isValidCharacterClass(value) {
    return /^\[(\^)?[a-zA-Z0-9_\-]+\]$/.test(value);
}

// validate quantifier format like {3}, {1,5}, or shorthand quantifiers *, +, ?
function isValidQuantifier(value) {
    return /^\{(\d+)(?:,(\d+))?\}$/.test(value) || /^[\*\+\?]$/.test(value);
}

// validate alternation format like (a|b|c), a single alternative inside parentheses should also be valid, useful for repeated sequences
function isValidAlternation(value) {
    return /^\([^()]+(?:\|[^()]+)+\)$/.test(value);
}

// handle drag start event with edit state check
function handleDragStart(e) {
    if (this.classList.contains('editing')) {
        e.preventDefault();
        return false;
    }
    
    this.classList.add('dragging');
    draggedToken = this;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', this.getAttribute('data-index'));
}

// pattern tokenizer for visual editor - works fine so far, note: more complex alternation needs more logic
function tokenizePattern(pattern) {
    const tokens = [];
    let i = 0;
    
    while (i < pattern.length) {
        if (pattern[i] === '\\') {
            // escape sequences
            const escapeChar = pattern[i+1] || '';
            const isNegated = escapeChar === 'D' || escapeChar === 'W' || escapeChar === 'S';
            
            // create escape token
            const escapeToken = {
                type: 'escape',
                value: '\\' + escapeChar,
                display: '\\' + escapeChar,
                isNegated: isNegated
            };
            tokens.push(escapeToken);
            i += 2;
            
            // check for quantifiers after escape sequence and attach to it
            if (i < pattern.length && (pattern[i] === '*' || pattern[i] === '+' || pattern[i] === '?')) {
                escapeToken.value += pattern[i];
                escapeToken.display += pattern[i];
                i++;
            }
        } else if (pattern[i] === '[') {
            // character class
            let endIdx = pattern.indexOf(']', i);
            if (endIdx === -1) endIdx = pattern.length;
            const classContent = pattern.substring(i, endIdx + 1);
            
            // character class token
            const classToken = {
                type: 'character-class',
                value: classContent,
                display: classContent
            };
            tokens.push(classToken);
            i = endIdx + 1;
            
            // check for quantifiers after character class and attach to it
            if (i < pattern.length && (pattern[i] === '*' || pattern[i] === '+' || pattern[i] === '?')) {
                classToken.value += pattern[i];
                classToken.display += pattern[i];
                i++;
            }
        } else if (pattern[i] === '{') {
            // quantifier
            let endIdx = pattern.indexOf('}', i);
            if (endIdx === -1) endIdx = pattern.length;
            const quantContent = pattern.substring(i, endIdx + 1);
            tokens.push({
                type: 'quantifier',
                value: quantContent,
                display: quantContent
            });
            i = endIdx + 1;
        } else if (pattern[i] === '(') {
            // alternation or group
            let nestLevel = 1;
            let endIdx = i + 1;
            
            while (nestLevel > 0 && endIdx < pattern.length) {
                if (pattern[endIdx] === '(') nestLevel++;
                if (pattern[endIdx] === ')') nestLevel--;
                endIdx++;
            }
            
            const groupContent = pattern.substring(i, endIdx);
            
            // create alternation token
            const altToken = {
                type: 'alternation',
                value: groupContent,
                display: groupContent
            };
            tokens.push(altToken);
            i = endIdx;
            
            // check for quantifiers after alternation and attach to it
            if (i < pattern.length && (pattern[i] === '*' || pattern[i] === '+' || pattern[i] === '?')) {
                altToken.value += pattern[i];
                altToken.display += pattern[i];
                i++;
            }
        } else if (pattern[i] === '.') {
            // any character
            const dotToken = {
                type: 'any-char',
                value: '.',
                display: '.'
            };
            tokens.push(dotToken);
            i++;
            
            // check for quantifiers after dot and attach to it
            if (i < pattern.length && (pattern[i] === '*' || pattern[i] === '+' || pattern[i] === '?')) {
                dotToken.value += pattern[i];
                dotToken.display += pattern[i];
                i++;
            }
        } else if (pattern[i] === '*' || pattern[i] === '+' || pattern[i] === '?') {
            // standalone quantifier (should be attached to previous token but handle for safety)
            tokens.push({
                type: 'quantifier',
                value: pattern[i],
                display: pattern[i]
            });
            i++;
        } else {
            // literal - collect consecutive literal characters
            let literalStart = i;
            while (i < pattern.length && 
                   !'\\[{(.?*+'.includes(pattern[i]) && 
                   (i === pattern.length - 1 || pattern[i+1] !== '{')) {
                i++;
            }
            const literalContent = pattern.substring(literalStart, i);
            
            // create literal token
            const literalToken = {
                type: 'literal',
                value: literalContent,
                display: literalContent
            };
            tokens.push(literalToken);
            
            // check for quantifiers after literal and attach to it
            if (i < pattern.length && (pattern[i] === '*' || pattern[i] === '+' || pattern[i] === '?')) {
                literalToken.value += pattern[i];
                literalToken.display += pattern[i];
                i++;
            }
        }
    }
    
    return tokens;
}

// convert tokens back to pattern string
function tokensToPattern(tokens) {
    return tokens.map(token => token.value).join('');
}

// apply the pattern from tokens
function applyPattern() {
    const pattern = tokensToPattern(currentTokens);
    
    if (currentEditField) {
        currentConfig.patterns[currentEditField] = pattern;
        renderPatternRows();
        closePatternModal();
    }
}

// preview the current pattern with samples of generated values
async function testPattern() {
    const pattern = tokensToPattern(currentTokens);
    if (!pattern) {
        document.getElementById('previewSamples').innerHTML = 
            '<div class="sample-item">Add some pattern components to see examples</div>';
        return;
    }
    
    try {
        const response = await fetch('/test-pattern', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                pattern: pattern,
                samples: 5,
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to test pattern');
        }
        
        const result = await response.json();
        
        // display sample values
        const previewContainer = document.getElementById('previewSamples');
        previewContainer.innerHTML = '';
        
        result.samples.forEach(sample => {
            const sampleElem = document.createElement('div');
            sampleElem.className = 'sample-item';
            sampleElem.textContent = sample;
            previewContainer.appendChild(sampleElem);
        });
    } catch (error) {
        console.error('Error testing pattern:', error);
        document.getElementById('previewSamples').innerHTML = 
            `<div class="sample-item error-sample">Error: ${error.message}</div>`;
    }
}

function closePatternModal() {
    document.getElementById('patternEditModal').style.display = 'none';
    currentEditField = '';
    currentTokens = [];
}

async function confirmSaveConfig() {
    const configName = document.getElementById('saveConfigName').value.trim();
    
    if (!configName) {
        alert('Please enter a configuration name');
        return;
    }
    
    let fileName = configName;
    if (!fileName.endsWith('.json')) {
        fileName += '.json';
    }
    
    try {
        const response = await fetch('/save-config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                config_name: fileName,
                config_data: currentConfig
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to save configuration');
        }
        
        const result = await response.json();
        
        if (result.success) {
            alert('Configuration saved successfully');
            document.getElementById('saveConfigModal').style.display = 'none';
            document.getElementById('patternBuilderModal').style.display = 'none';
            
            // reload configs list
            loadConfigs();
        } else {
            alert('Failed to save configuration: ' + result.message);
        }
    } catch (error) {
        console.error('Error saving config:', error);
        alert('Failed to save configuration: ' + error.message);
    }
}

function closePatternBuilder() {
    if (confirm('Discard all changes?')) {
        document.getElementById('patternBuilderModal').style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', function() {

    const tooltips = document.querySelectorAll('.tooltip');
    tooltips.forEach(tooltip => {
        const tooltipText = tooltip.querySelector('.tooltiptext');
        tooltip.addEventListener('mouseover', () => {
            tooltipText.style.visibility = 'visible';
            tooltipText.style.opacity = '0.9';
        });
        tooltip.addEventListener('mouseout', () => {
            tooltipText.style.visibility = 'hidden';
            tooltipText.style.opacity = '0';
        });
    });
});

let currentConfig = {
    headers: [],
    patterns: {}
};

async function loadConfigs() {
    try {
        const response = await fetch('/list-configs', {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Failed to load configurations');
        }
        
        const result = await response.json();
        configs = result.configs;
        
        // populate config selection
        const configSelect = document.getElementById('configSelect');
        
        while (configSelect.options.length > 1) {
            configSelect.remove(1);
        }
        
        // add configurations to dropdown
        configs.forEach(config => {
            const option = document.createElement('option');
            option.value = config;
            option.textContent = config;
            configSelect.appendChild(option);
        });
        
        // if we have configurations, select the first one
        if (configs.length > 0) {
            configSelect.value = configs[0];
            loadSelectedConfig();
        } else {
            // no configurations, select "Create New"
            configSelect.value = "new";
            createNewConfig();
        }
    } catch (error) {
        console.error('Error loading configs:', error);
        alert('Failed to load configurations: ' + error.message);
    }
}

async function loadSelectedConfig() {
    const configSelect = document.getElementById('configSelect');
    const selectedConfig = configSelect.value;
    
    // handle "Create New" option
    if (selectedConfig === "new") {
        createNewConfig();
        return;
    }
    
    try {
        const response = await fetch('/get-config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                config: selectedConfig
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to load configuration');
        }
        
        const result = await response.json();
        currentConfig = result.config;
        document.getElementById('configNameContainer').style.display = 'none';
        
        renderPatternRows();
        
        const previewView = document.getElementById('previewView');
        if (previewView.classList.contains('active')) {
            updateGeneratePreview();
        }
    } catch (error) {
        console.error('Error loading config:', error);
        alert('Failed to load configuration: ' + error.message);
    }
}

function createNewConfig() {
    currentConfig = {
        headers: [],
        patterns: {}
    };
    
    const configNameContainer = document.getElementById('configNameContainer');
    configNameContainer.style.display = 'block';
    document.getElementById('configNameInput').value = 'new_config.json';
    
    renderPatternRows();
}

function renderPatternRows() {
    const rowsContainer = document.getElementById('patternRows');
    rowsContainer.innerHTML = '';
    
    if (!currentConfig || !currentConfig.headers || !currentConfig.patterns) {
        console.warn('No valid configuration to render');
        return;
    }
    
    currentConfig.headers.forEach(header => {
        const pattern = currentConfig.patterns[header] || '';
        
        const row = document.createElement('div');
        row.className = 'pattern-row';
        
    // pattern name cell
        const nameCell = document.createElement('div');
        nameCell.className = 'pattern-name';
        nameCell.textContent = header;
        row.appendChild(nameCell);
        
    // pattern value cell
        const valueCell = document.createElement('div');
        valueCell.className = 'pattern-value';
        valueCell.textContent = pattern;
        row.appendChild(valueCell);
        
    // controls cell
        const controlsCell = document.createElement('div');
        controlsCell.className = 'pattern-controls';
        
    // edit pattern
        const editButton = document.createElement('button');
        editButton.className = 'btn-icon';
        editButton.textContent = 'Edit';
        editButton.onclick = function() { editPattern(header); };
        controlsCell.appendChild(editButton);
        
    // delete pattern
        const deleteButton = document.createElement('button');
        deleteButton.className = 'btn-icon';
        deleteButton.textContent = 'Delete';
        deleteButton.onclick = function() { deletePattern(header); };
        controlsCell.appendChild(deleteButton);
        
        row.appendChild(controlsCell);
        rowsContainer.appendChild(row);
    });
}

function addNewField() {
    const fieldName = document.getElementById('newFieldName').value.trim();
    
    if (!fieldName) {
        alert('Please enter a field name');
        return;
    }
    
    if (currentConfig.headers.includes(fieldName)) {
        alert('Field already exists');
        return;
    }
    
    currentConfig.headers.push(fieldName);
    currentConfig.patterns[fieldName] = '';
    
    document.getElementById('newFieldName').value = '';
    renderPatternRows();
}

function saveConfig() {
    // should have at least one field
    if (currentConfig.headers.length === 0) {
        alert('Configuration must have at least one field');
        return;
    }
    
    // ensure that a pattern is defined for each field
    // tell the user which fields are missing patterns
    let missingPatterns = [];
    currentConfig.headers.forEach(header => {
        if (!currentConfig.patterns[header]) {
            missingPatterns.push(header);
        }
    });
    
    if (missingPatterns.length > 0) {
        alert(`Please define patterns for these fields: ${missingPatterns.join(', ')}`);
        return;
    }
    
    // for a new configuration, use the value from configNameInput
    // for existing configurations, use the selected value from the dropdown
    const configSelect = document.getElementById('configSelect');
    let configName;
    
    if (configSelect.value === "new") {
        configName = document.getElementById('configNameInput').value.trim();
        if (!configName) {
            alert('Please enter a configuration name');
            return;
        }
    } else {
        configName = configSelect.value;
    }
    
    if (!configName.endsWith('.json')) {
        configName += '.json';
    }
    
    // show confirmation for overwriting existing config
    if (configs.includes(configName) && !confirm(`Configuration "${configName}" already exists. Overwrite?`)) {
        return;
    }
    
    saveConfigToServer(configName);
}

async function saveConfigToServer(configName) {
    try {
        const response = await fetch('/save-config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                config_name: configName,
                config_data: currentConfig
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to save configuration');
        }
        
        const result = await response.json();
        
        if (result.success) {
            alert('Configuration saved successfully');
            
            // reload configs and select the newly saved one
            await loadConfigs();
            const configSelect = document.getElementById('configSelect');
            configSelect.value = configName;
            loadSelectedConfig();
        } else {
            alert('Failed to save configuration: ' + result.message);
        }
    } catch (error) {
        console.error('Error saving config:', error);
        alert('Failed to save configuration: ' + error.message);
    }
}

document.addEventListener('DOMContentLoaded', function() {

    loadConfigs(); // load available configurations on page load
    
    const tooltips = document.querySelectorAll('.tooltip');
    tooltips.forEach(tooltip => {
        const tooltipText = tooltip.querySelector('.tooltiptext');
        tooltip.addEventListener('mouseover', () => {
            tooltipText.style.visibility = 'visible';
            tooltipText.style.opacity = '0.9';
        });
        tooltip.addEventListener('mouseout', () => {
            tooltipText.style.visibility = 'hidden';
            tooltipText.style.opacity = '0';
        });
    });
    
    const generateOutputFormat = document.querySelector('#generateForm select[name="format"]');
    if (generateOutputFormat) {
        generateOutputFormat.id = 'generateOutputFormat';
    }
});

function showGenerateView(viewId, button) {
    document.querySelectorAll('.generate-nav .nav-button').forEach(btn => {
        btn.classList.remove('active');
    });
    button.classList.add('active');
    
    document.querySelectorAll('.view-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    document.getElementById(viewId + 'View').classList.add('active');
    
    if (viewId === 'preview') {
        updateGeneratePreview();
    }
}

async function updateGeneratePreview() {
    const configSelect = document.getElementById('configSelect');
    const selectedConfig = configSelect.value;
    const format = document.getElementById('generateOutputFormat').value;
    const previewData = document.getElementById('generatePreviewData');
    
    // only show preview if we have a valid config
    if (selectedConfig === 'new' || !selectedConfig) {
        previewData.textContent = 'Please save your configuration before previewing data.';
        return;
    }
    
    previewData.textContent = 'Loading preview...';
    
    try {
        const response = await fetch('/generate-preview', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                config: selectedConfig,
                format: format,
                rows: 25
            })
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        const result = await response.json();
        
        if (result.type === 'preview') {
            previewData.className = `preview-data ${format}-view`;
            
            if (format === 'sqlite') {
                previewData.innerHTML = result.data;    // HTML for grid view
            } else {
                previewData.textContent = result.data;  // text for other formats
            }
        } else {
            previewData.textContent = 'Error: ' + result.message;
        }
    } catch (error) {
        previewData.textContent = 'Error: ' + error.message;
    }
}

function handleGenerateFormatChange() {
    // only update preview if the preview view is active
    const previewView = document.getElementById('previewView');
    if (previewView.classList.contains('active')) {
        updateGeneratePreview();
    }
}