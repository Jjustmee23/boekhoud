/**
 * Playful Loading Animations
 * JavaScript voor speelse laadanimaties
 */

class LoadingAnimations {
    constructor() {
        this.overlay = null;
        this.progressBar = null;
        this.animationType = 'invoice'; // Standaard animatie
        this.messages = {
            invoice: [
                'Facturen klaarmaken...',
                'Bezig met berekenen...',
                'BTW-bedragen controleren...',
                'Factuurnummer genereren...',
                'Bijna klaar!'
            ],
            customer: [
                'Klantgegevens laden...',
                'Contactinformatie controleren...',
                'BTW-nummer valideren...',
                'Adresgegevens verwerken...',
                'Bezig met verwerken...'
            ],
            report: [
                'Rapport genereren...',
                'Gegevens verzamelen...',
                'Cijfers analyseren...',
                'Grafieken voorbereiden...',
                'Rapport samenstellen...'
            ],
            vat: [
                'BTW berekeningen uitvoeren...',
                'Facturen verzamelen...',
                'Aangifte voorbereiden...',
                'BTW percentages controleren...',
                'Roosters berekenen...'
            ],
            excel: [
                'Excel bestand aanmaken...',
                'Werkblad voorbereiden...',
                'Cellen formatteren...',
                'Formules toepassen...',
                'Download voorbereiden...'
            ],
            csv: [
                'CSV bestand genereren...',
                'Gegevens exporteren...',
                'Komma-gescheiden waarden voorbereiden...',
                'Download klaarmaken...'
            ],
            default: [
                'Even geduld...',
                'Bezig met laden...',
                'Gegevens verwerken...',
                'Bijna klaar!'
            ]
        };
        this.currentMessageIndex = 0;
        this.messageInterval = null;
        this.init();
    }

    init() {
        // Voeg overlay toe aan de DOM als deze nog niet bestaat
        if (!document.querySelector('.loading-overlay')) {
            this.createOverlay();
        }

        // Event listeners voor formulieren
        this.setupEventListeners();
    }

    createOverlay() {
        // Creëer de overlay
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        
        // Maak de animatie containers
        overlay.innerHTML = `
            <div class="animation-container">
                <!-- Invoice spinner -->
                <div class="invoice-spinner animation" data-animation="invoice"></div>
                
                <!-- Dancing euro -->
                <div class="dancing-euro animation" data-animation="customer" style="display: none;">
                    <i class="fas fa-euro-sign"></i>
                </div>
                
                <!-- Stacking docs -->
                <div class="stacking-docs animation" data-animation="report" style="display: none;">
                    <div class="doc"></div>
                    <div class="doc"></div>
                    <div class="doc"></div>
                </div>
                
                <!-- Calculator -->
                <div class="calculator animation" data-animation="vat" style="display: none;">
                    ${this.createCalculatorKeys()}
                </div>
                
                <!-- Excel animation -->
                <div class="excel-animation animation" data-animation="excel" style="display: none;">
                    <div class="excel-grid">
                        <div class="excel-cell"></div>
                        <div class="excel-cell"></div>
                        <div class="excel-cell"></div>
                        <div class="excel-cell"></div>
                        <div class="excel-cell"></div>
                        <div class="excel-cell"></div>
                        <div class="excel-cell"></div>
                        <div class="excel-cell"></div>
                        <div class="excel-cell"></div>
                    </div>
                </div>
                
                <!-- CSV animation -->
                <div class="csv-animation animation" data-animation="csv" style="display: none;">
                    <div class="csv-line"></div>
                    <div class="csv-line"></div>
                    <div class="csv-line"></div>
                </div>
                
                <!-- Progress bar -->
                <div class="progress-bar-container">
                    <div class="progress-bar"></div>
                </div>
                
                <!-- Message -->
                <div class="loading-message">Bezig met laden...</div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        this.overlay = overlay;
        this.progressBar = overlay.querySelector('.progress-bar');
    }

    createCalculatorKeys() {
        const keys = ['7', '8', '9', '4', '5', '6', '1', '2', '3', '0', '+', '='];
        let html = '';
        
        keys.forEach((key, index) => {
            html += `<div class="calculator-key" style="--key-index: ${index}">${key}</div>`;
        });
        
        return html;
    }

    setupEventListeners() {
        // Vang alle formulier submits op voor animatie
        document.addEventListener('submit', (e) => {
            const form = e.target;
            
            // Controleer of het formulier geen data-no-animation attribuut heeft
            if (!form.hasAttribute('data-no-animation')) {
                // Bepaal het type actie op basis van het formulier
                this.determineAnimationType(form);
                
                // Toon de animatie
                this.show();
                
                // Voeg een kleine vertraging toe om te voorkomen dat de animatie direct verdwijnt
                setTimeout(() => {
                    this.updateProgress(30);
                }, 500);
            }
        });

        // Vang alle linkclicks op die data-show-animation hebben
        document.addEventListener('click', (e) => {
            if (e.target.closest('[data-show-animation]')) {
                const animationType = e.target.closest('[data-show-animation]').getAttribute('data-show-animation');
                if (animationType) {
                    this.setAnimationType(animationType);
                }
                this.show();
            }
        });

        // Voeg AJAX interception toe (voor fetch en XMLHttpRequest)
        this.interceptAjaxRequests();
    }

    interceptAjaxRequests() {
        // Intercept fetch
        const originalFetch = window.fetch;
        window.fetch = (...args) => {
            const url = args[0];
            const options = args[1] || {};
            
            // Alleen animatie tonen voor niet-GET requests (POST, PUT, DELETE)
            if (options.method && options.method !== 'GET') {
                this.determineAnimationTypeFromUrl(url);
                this.show();
            }
            
            return originalFetch(...args)
                .then(response => {
                    if (options.method && options.method !== 'GET') {
                        this.updateProgress(100);
                        setTimeout(() => this.hide(), 500);
                    }
                    return response;
                })
                .catch(error => {
                    this.hide();
                    throw error;
                });
        };
        
        // Intercept XMLHttpRequest
        const originalXhrOpen = XMLHttpRequest.prototype.open;
        const originalXhrSend = XMLHttpRequest.prototype.send;
        const self = this;
        
        XMLHttpRequest.prototype.open = function(...args) {
            this._method = args[0];
            this._url = args[1];
            originalXhrOpen.apply(this, args);
        };
        
        XMLHttpRequest.prototype.send = function(...args) {
            if (this._method && this._method !== 'GET') {
                self.determineAnimationTypeFromUrl(this._url);
                self.show();
                
                this.addEventListener('load', () => {
                    self.updateProgress(100);
                    setTimeout(() => self.hide(), 500);
                });
                
                this.addEventListener('error', () => {
                    self.hide();
                });
            }
            
            originalXhrSend.apply(this, args);
        };
    }

    determineAnimationType(form) {
        const formAction = form.getAttribute('action') || '';
        const formId = form.getAttribute('id') || '';
        
        this.determineAnimationTypeFromUrl(formAction, formId);
    }

    determineAnimationTypeFromUrl(url, formId = '') {
        // Reset naar standaard
        let type = 'default';
        
        // Controleer op basis van URL en form ID
        if (url.includes('invoice') || url.includes('factuur') || formId.includes('invoice')) {
            type = 'invoice';
        } else if (url.includes('customer') || url.includes('klant') || formId.includes('customer')) {
            type = 'customer';
        } else if (url.includes('report') || url.includes('rapport') || formId.includes('report')) {
            type = 'report';
        } else if (url.includes('vat') || url.includes('btw') || formId.includes('vat')) {
            type = 'vat';
        } else if (url.includes('excel') || url.includes('xlsx') || url.includes('export_format=excel')) {
            type = 'excel';
        } else if (url.includes('csv') || url.includes('export_format=csv')) {
            type = 'csv';
        }
        
        // We geven voorrang aan data-show-animation attribuut als die is ingesteld
        const button = document.activeElement;
        if (button && button.hasAttribute && button.hasAttribute('data-show-animation')) {
            type = button.getAttribute('data-show-animation');
        }
        
        this.setAnimationType(type);
    }

    setAnimationType(type) {
        this.animationType = type;
        
        // Reset message index
        this.currentMessageIndex = 0;
        
        // Verberg alle animaties
        const animations = this.overlay.querySelectorAll('.animation');
        animations.forEach(animation => {
            animation.style.display = 'none';
        });
        
        // Toon de juiste animatie
        const targetAnimation = this.overlay.querySelector(`[data-animation="${type}"]`);
        if (targetAnimation) {
            targetAnimation.style.display = 'flex';
        } else {
            // Fallback naar invoice animation
            this.overlay.querySelector('[data-animation="invoice"]').style.display = 'flex';
        }
        
        // Update CSS class op overlay
        this.overlay.className = 'loading-overlay';
        this.overlay.classList.add(`loading-${type}`);
        
        // Update bericht
        this.updateMessage();
    }

    updateMessage() {
        const messages = this.messages[this.animationType] || this.messages.default;
        const messageElement = this.overlay.querySelector('.loading-message');
        
        if (messageElement) {
            messageElement.textContent = messages[this.currentMessageIndex];
            
            // Clear existing interval
            if (this.messageInterval) {
                clearInterval(this.messageInterval);
            }
            
            // Stel een interval in om berichten te roteren
            this.messageInterval = setInterval(() => {
                this.currentMessageIndex = (this.currentMessageIndex + 1) % messages.length;
                messageElement.textContent = messages[this.currentMessageIndex];
            }, 2000);
        }
    }

    show() {
        if (this.overlay) {
            this.overlay.classList.add('active');
            this.resetProgress();
        }
    }

    hide() {
        if (this.overlay) {
            this.overlay.classList.remove('active');
            
            // Clear message interval
            if (this.messageInterval) {
                clearInterval(this.messageInterval);
                this.messageInterval = null;
            }
        }
    }

    resetProgress() {
        if (this.progressBar) {
            this.progressBar.style.width = '0%';
        }
    }

    updateProgress(percentage) {
        if (this.progressBar) {
            this.progressBar.style.width = `${percentage}%`;
            
            // Auto hide when reaching 100%
            if (percentage >= 100) {
                setTimeout(() => this.hide(), 500);
            }
        }
    }
}

// Initialiseer de animaties zodra de DOM geladen is
document.addEventListener('DOMContentLoaded', () => {
    window.loadingAnimations = new LoadingAnimations();
});

// Helper functie om animaties handmatig te tonen
function showLoadingAnimation(type = 'default') {
    if (window.loadingAnimations) {
        window.loadingAnimations.setAnimationType(type);
        window.loadingAnimations.show();
        return window.loadingAnimations;
    }
    return null;
}