// AI Settings - Dynamic LLM Provider and Model Selection
// Like Cline in VS Code: provider dropdown updates model dropdown automatically

frappe.ui.form.on('AI Settings', {
    refresh(frm) {
        // Initialize: fetch models for current provider on load
        setTimeout(() => {
            update_model_dropdown(frm);
        }, 500);
    },
    
    llm_provider(frm) {
        // When provider changes, update model dropdown and show/hide API key field
        update_model_dropdown(frm);
        toggle_api_key_field(frm);
        toggle_base_url_field(frm);
    },
    
    api_key(frm) {
        // When API key changes, re-fetch models (for providers that need it)
        const provider = frm.doc.llm_provider;
        if (['openrouter', 'together', 'groq', 'anthropic', 'openai', 'gemini', 'mistral'].includes(provider)) {
            update_model_dropdown(frm);
        }
    },
    
    custom_api_base_url(frm) {
        // When base URL changes, re-fetch models for local providers
        const provider = frm.doc.llm_provider;
        if (provider === 'ollama' || provider === 'lm_studio' || provider === 'custom') {
            update_model_dropdown(frm);
        }
    }
});

function update_model_dropdown(frm) {
    const provider = frm.doc.llm_provider;
    if (!provider) return;
    
    const modelField = frm.fields_dict.llm_model;
    if (!modelField) return;
    
    // Show loading state
    modelField.df.options = "Loading models...";
    frm.refresh_field('llm_model');
    
    // Fetch models from backend
    frappe.call({
        method: 'erp_ai.api.list_available_models',
        args: {
            provider: provider,
            api_key: frm.doc.api_key || '',
            base_url: frm.doc.custom_api_base_url || ''
        },
        callback: function(r) {
            if (!r.message) {
                console.warn('No models returned for provider:', provider);
                return;
            }
            
            // Build options string: "value|label\nvalue|label"
            let options = '';
            r.message.forEach(function(model) {
                const value = model.id || model.name;
                const label = model.name || model.id || value;
                options += value + '|' + label + '\n';
            });
            
            if (!options) {
                options = 'no_models|No models available (check API key or connection)';
            }
            
            modelField.df.options = options;
            frm.refresh_field('llm_model');
            
            // If current model still exists, keep it; otherwise select first
            const currentModel = frm.doc.llm_model;
            const modelExists = r.message.some(function(m) {
                return m.id === currentModel || m.name === currentModel;
            });
            
            if (!modelExists && r.message.length > 0) {
                frm.set_value('llm_model', r.message[0].id);
            }
        },
        error: function(err) {
            console.error('Failed to fetch models:', err);
            modelField.df.options = 'error|Error loading models (see console)';
            frm.refresh_field('llm_model');
        }
    });
}

function toggle_api_key_field(frm) {
    const provider = frm.doc.llm_provider;
    const apiKeyField = frm.fields_dict.api_key;
    if (!apiKeyField) return;
    
    // Cloud providers require API key, local providers don't
    const requiresApiKey = ['openrouter', 'together', 'groq', 'anthropic', 'openai', 'gemini', 'mistral'].includes(provider);
    
    if (requiresApiKey) {
        apiKeyField.df.hidden = 0;
        apiKeyField.df.reqd = 1;
        apiKeyField.df.description = 'Enter your API key for ' + provider + '.';
    } else {
        apiKeyField.df.hidden = 1;
        apiKeyField.df.reqd = 0;
        apiKeyField.df.description = 'Leave blank for local providers.';
    }
    
    frm.refresh_field('api_key');
    
    // Clear API key if switching to local provider
    if (!requiresApiKey && frm.doc.api_key) {
        frm.set_value('api_key', '');
    }
}

function toggle_base_url_field(frm) {
    const provider = frm.doc.llm_provider;
    const baseUrlField = frm.fields_dict.custom_api_base_url;
    if (!baseUrlField) return;
    
    // Base URL is relevant for local providers and custom API
    const requiresBaseUrl = ['ollama', 'lm_studio', 'custom'].includes(provider);
    
    if (requiresBaseUrl) {
        baseUrlField.df.hidden = 0;
        baseUrlField.df.reqd = 0;
        if (provider === 'ollama') {
            baseUrlField.df.description = 'Ollama URL (default: http://localhost:11434)';
        } else if (provider === 'lm_studio') {
            baseUrlField.df.description = 'LM Studio URL (default: http://localhost:1234/v1)';
        } else {
            baseUrlField.df.description = 'Custom OpenAI-compatible API base URL';
        }
    } else {
        baseUrlField.df.hidden = 1;
        baseUrlField.df.reqd = 0;
        baseUrlField.df.description = '';
    }
    
    frm.refresh_field('custom_api_base_url');
}
