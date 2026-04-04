/**
 * Admin Organization Generators
 * Handles "Generate Org ID" button
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
        // Find the button
        const generateOrgIdBtn = document.getElementById('generate-org-id-btn');

        if (generateOrgIdBtn) {
            generateOrgIdBtn.addEventListener('click', handleGenerateOrgId);
        }

        // Add info box about auto-generation
        addAutoGenerationInfo();
    }

    /**
     * Generate Org ID button handler
     */
    function handleGenerateOrgId(e) {
        e.preventDefault();
        
        const orgIdField = document.getElementById('id_org_id');
        
        if (!orgIdField) {
            showError('Organization ID field not found.');
            return;
        }

        // Disable button and show loading
        e.target.disabled = true;
        e.target.textContent = 'Generating...';

        // Make AJAX request
        const url = '/admin/accounts/organization/generate-org-id/';
        
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
            } else if (data.org_id) {
                orgIdField.value = data.org_id;
                orgIdField.focus();
                showSuccess(`Generated Organization ID: ${data.org_id}`);
                
                // Flash the field to draw attention
                flashField(orgIdField);
            }
        })
        .catch(error => {
            showError('Failed to generate Organization ID. Please try again.');
            console.error('Generate Org ID error:', error);
        })
        .finally(() => {
            e.target.disabled = false;
            e.target.textContent = 'Generate Org ID';
        });
    }

    /**
     * Add informational box about auto-generation
     */
    function addAutoGenerationInfo() {
        const orgIdField = document.getElementById('id_org_id');
        if (!orgIdField) return;

        // Check if we're on the "add" page (not edit)
        const isAddPage = window.location.pathname.includes('/add/');
        if (!isAddPage) return;

        const fieldGroup = orgIdField.closest('.form-row') || orgIdField.closest('div');
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
            <strong>💡 Auto-Generation:</strong> When creating a new organization, the Organization ID 
            will be automatically generated if left blank. You can also use the button above to 
            generate it manually before saving.
        `;

        // Insert after the org_id field's form row
        if (fieldGroup.parentNode) {
            fieldGroup.parentNode.insertBefore(infoBox, fieldGroup.nextSibling);
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