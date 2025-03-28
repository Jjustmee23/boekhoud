/**
 * JavaScript voor de Email OAuth Admin pagina
 * Bevat functies voor het testen en beheren van OAuth email instellingen
 */

document.addEventListener('DOMContentLoaded', function() {
    // Toggle password visibility voor client secret
    const toggleButton = document.getElementById('toggle-secret');
    const clientSecretField = document.getElementById('ms_graph_client_secret');
    
    if (toggleButton && clientSecretField) {
        toggleButton.addEventListener('click', function() {
            const type = clientSecretField.getAttribute('type') === 'password' ? 'text' : 'password';
            clientSecretField.setAttribute('type', type);
            toggleButton.innerHTML = type === 'password' ? 
                '<i class="bi bi-eye"></i> Toon' : 
                '<i class="bi bi-eye-slash"></i> Verberg';
        });
    }
    
    // Validatie van formulier
    const oauthForm = document.getElementById('oauth-email-form');
    if (oauthForm) {
        oauthForm.addEventListener('submit', function(event) {
            // Controleer of de client secret een valide waarde heeft
            const clientSecret = clientSecretField.value;
            if (clientSecret && clientSecret.includes('client_id')) {
                event.preventDefault();
                alert('Let op! Het lijkt erop dat je de Client Secret ID hebt ingevoerd in plaats van de Client Secret Value. ' +
                      'Zorg ervoor dat je de geheime sleutel gebruikt en niet de ID van de sleutel.');
            }
        });
    }
    
    // Tooltip initialisatie voor help icons
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Test functie voor OAuth e-mail validatie
function validateOAuthSettings() {
    const clientId = document.getElementById('ms_graph_client_id').value;
    const clientSecret = document.getElementById('ms_graph_client_secret').value;
    const tenantId = document.getElementById('ms_graph_tenant_id').value;
    const senderEmail = document.getElementById('ms_graph_sender_email').value;
    
    // Eenvoudige frontend validatie
    if (!clientId || !tenantId || !senderEmail) {
        showValidationResult(false, 'Vul alle verplichte velden in.');
        return;
    }
    
    // Als er geen client secret is ingevuld, maar er is wel een bestaand secret (placeholder), toon waarschuwing
    const secretPlaceholder = document.getElementById('ms_graph_client_secret').getAttribute('placeholder');
    if (!clientSecret && secretPlaceholder && secretPlaceholder.includes('•')) {
        showValidationResult('warning', 'Let op: Je gebruikt het bestaande client secret. Als dit niet werkt, voer dan een nieuw secret in.');
        return;
    }
    
    // Validatie voor Microsoft 365 Client Secret format
    if (clientSecret && (
        clientSecret.startsWith('ClientSecret_') || 
        clientSecret.includes('client_id') || 
        clientSecret.includes('secret_id')
    )) {
        showValidationResult(false, 'Het lijkt erop dat je de Client Secret ID hebt ingevoerd in plaats van de Client Secret Value. ' +
                                  'Gebruik de geheime sleutel waarde, niet de ID van de sleutel.');
        return;
    }
    
    showValidationResult(true, 'De instellingen lijken geldig te zijn. Klik op "Instellingen Opslaan" om deze op te slaan en test daarna de e-mail functionaliteit.');
}

// Toont het resultaat van de OAuth validatie
function showValidationResult(success, message) {
    const resultContainer = document.getElementById('validation-result');
    if (!resultContainer) return;
    
    if (success === 'warning') {
        resultContainer.innerHTML = `
            <div class="alert alert-warning alert-dismissible fade show mt-3" role="alert">
                <i class="bi bi-exclamation-triangle-fill me-2"></i> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
    } else if (success) {
        resultContainer.innerHTML = `
            <div class="alert alert-success alert-dismissible fade show mt-3" role="alert">
                <i class="bi bi-check-circle-fill me-2"></i> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
    } else {
        resultContainer.innerHTML = `
            <div class="alert alert-danger alert-dismissible fade show mt-3" role="alert">
                <i class="bi bi-x-circle-fill me-2"></i> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
    }
}