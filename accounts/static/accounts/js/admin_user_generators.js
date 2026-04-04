/**
 * Admin User Generators
 * Handles "Generate User ID" and "Generate Password" buttons
 */

(function() {
    'use strict';

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        // Find the buttons
        const generateUserIdBtn = document.getElementById('generate-user-id-btn');
        const generatePasswordBtn = document.getElementById('generate-password-btn');

        if (generateUserIdBtn) {
            generateUserIdBtn.addEventListener('click', handleGenerateUserId);
        }

        if (generatePasswordBtn) {
            generatePasswordBtn.addEventListener('click', handleGeneratePassword);
        }

        // Add info box about auto-generation
        addAutoGenerationInfo();
    }

    /**
     * Generate User ID button handler
     */
    function handleGenerateUserId(e) {
        e.preventDefault();
        
        const orgField = document.getElementById('id_organization');
        const usernameField = document.getElementById('id_username');
        
        if (!orgField || !orgField.value) {
            showError('Please select an organization first.');
            return;
        }

        // Disable button and show loading
        e.target.disabled = true;
        e.target.textContent = 'Generating...';

        // Make AJAX request
        const url = `/admin/accounts/user/generate-user-id/?org_pk=${orgField.value}`;
        
        fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin'
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError(data.error);
            } else if (data.user_id) {
                usernameField.value = data.user_id;
                usernameField.focus();
                showSuccess(`Generated User ID: ${data.user_id}`);
                
                // Flash the field to draw attention
                flashField(usernameField);
            }
        })
        .catch(error => {
            showError('Failed to generate User ID. Please try again.');
            console.error('Generate User ID error:', error);
        })
        .finally(() => {
            e.target.disabled = false;
            e.target.textContent = '⚡ Generate User ID';
        });
    }

    /**
     * Generate Password button handler
     */
    function handleGeneratePassword(e) {
        e.preventDefault();
        
        const passwordField = document.getElementById('id_raw_password');
        
        if (!passwordField) {
            showError('Password field not found.');
            return;
        }

        // Disable button and show loading
        e.target.disabled = true;
        e.target.textContent = 'Generating...';

        // Make AJAX request
        const url = '/admin/accounts/user/generate-password/';
        
        fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin'
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError(data.error);
            } else if (data.password) {
                passwordField.value = data.password;
                passwordField.select(); // Select text for easy copying
                showSuccess('Password generated! Copy it now - it won\'t be shown again after saving.');
                
                // Flash the field to draw attention
                flashField(passwordField);
            }
        })
        .catch(error => {
            showError('Failed to generate password. Please try again.');
            console.error('Generate Password error:', error);
        })
        .finally(() => {
            e.target.disabled = false;
            e.target.textContent = '🔑 Generate Password';
        });
    }

    /**
     * Add informational box about auto-generation
     */
    function addAutoGenerationInfo() {
        const usernameField = document.getElementById('id_username');
        if (!usernameField) return;

        // Check if we're on the "add" page (not edit)
        const isAddPage = window.location.pathname.includes('/add/');
        if (!isAddPage) return;

        const fieldGroup = usernameField.closest('.form-row') || usernameField.closest('div');
        if (!fieldGroup) return;

        // Create info box
        const infoBox = document.createElement('div');
        infoBox.className = 'auto-gen-info';
        infoBox.style.cssText = `
            background: #e8f4f8;
            border-left: 4px solid #2196F3;
            padding: 12px;
            margin: 10px 0;
            font-size: 13px;
            line-height: 1.5;
        `;
        infoBox.innerHTML = `
            <strong>💡 Auto-Generation:</strong> When creating a new user, both User ID and Password 
            will be automatically generated if left blank. You can also use the buttons above to 
            generate them manually before saving.
        `;

        // Insert after the password field's form row
        const passwordField = document.getElementById('id_raw_password');
        if (passwordField) {
            const passwordFieldGroup = passwordField.closest('.form-row') || passwordField.closest('div');
            if (passwordFieldGroup && passwordFieldGroup.parentNode) {
                passwordFieldGroup.parentNode.insertBefore(infoBox, passwordFieldGroup.nextSibling);
            }
        }
    }

    /**
     * Show success message
     */
    function showSuccess(message) {
        showMessage(message, 'success');
    }

    /**
     * Show error message
     */
    function showError(message) {
        showMessage(message, 'error');
    }

    /**
     * Show message in Django admin style
     */
    function showMessage(message, type) {
        // Remove existing messages
        const existingMessages = document.querySelectorAll('.generator-message');
        existingMessages.forEach(msg => msg.remove());

        const messageDiv = document.createElement('div');
        messageDiv.className = `generator-message messagelist ${type === 'error' ? 'error' : 'success'}`;
        messageDiv.style.cssText = 'margin: 10px 0; padding: 10px;';
        
        const messageItem = document.createElement('li');
        messageItem.className = type === 'error' ? 'error' : 'success';
        messageItem.textContent = message;
        messageDiv.appendChild(messageItem);

        // Insert at the top of the content
        const content = document.querySelector('.content') || document.querySelector('form');
        if (content) {
            content.insertBefore(messageDiv, content.firstChild);
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                messageDiv.style.transition = 'opacity 0.5s';
                messageDiv.style.opacity = '0';
                setTimeout(() => messageDiv.remove(), 500);
            }, 5000);
        }
    }

    /**
     * Flash a field to draw attention
     */
    function flashField(field) {
        const originalBackground = field.style.background;
        field.style.transition = 'background 0.3s';
        field.style.background = '#fff59d';
        
        setTimeout(() => {
            field.style.background = originalBackground;
        }, 1000);
    }

})();
