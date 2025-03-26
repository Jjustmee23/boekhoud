/**
 * Main JavaScript functions for the Facturatie & Boekhouding application
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initTooltips();
    
    // Format currency inputs
    formatCurrencyInputs();
    
    // Handle invoice calculation
    setupInvoiceCalculations();
    
    // Customer form validations
    setupCustomerFormValidation();
    
    // VAT report period selection
    setupVatReportPeriodSelection();
});

/**
 * Initialize Bootstrap tooltips
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Format currency input fields
 */
function formatCurrencyInputs() {
    const currencyInputs = document.querySelectorAll('input[data-type="currency"]');
    
    currencyInputs.forEach(input => {
        input.addEventListener('blur', function(e) {
            // Format the number with 2 decimal places
            const value = parseFloat(this.value.replace(/[^\d.-]/g, ''));
            if (!isNaN(value)) {
                this.value = value.toFixed(2);
            }
        });
    });
}

/**
 * Set up calculations for invoice form
 */
function setupInvoiceCalculations() {
    const amountInclVat = document.getElementById('amount_incl_vat');
    const amountExclVat = document.getElementById('amount_excl_vat');
    const vatRate = document.getElementById('vat_rate');
    const customerSelect = document.getElementById('customer_id');
    
    if (amountInclVat && amountExclVat && vatRate) {
        // Calculate amount excluding VAT when inputs change
        function calculateExclVat() {
            const inclVatValue = parseFloat(amountInclVat.value) || 0;
            const vatRateValue = parseFloat(vatRate.value) || 0;
            
            if (inclVatValue > 0) {
                const exclVatValue = inclVatValue / (1 + (vatRateValue / 100));
                amountExclVat.value = exclVatValue.toFixed(2);
            } else {
                amountExclVat.value = "0.00";
            }
        }
        
        // Initial calculation
        calculateExclVat();
        
        // Update on change
        amountInclVat.addEventListener('input', calculateExclVat);
        vatRate.addEventListener('change', calculateExclVat);
    }
    
    // Auto-fill VAT rate when customer is selected
    if (customerSelect && vatRate) {
        customerSelect.addEventListener('change', function() {
            // Controleer of er een optie is geselecteerd
            if (this.selectedIndex <= 0) return;
            
            // Get selected option
            const selectedOption = this.options[this.selectedIndex];
            // Get data-default-vat-rate attribute (default BTW-tarief voor de klant)
            const defaultVatRate = selectedOption.getAttribute('data-default-vat-rate');
            
            // Set VAT rate if available and not empty/null/undefined
            if (defaultVatRate && 
                defaultVatRate !== 'null' && 
                defaultVatRate !== 'undefined' && 
                defaultVatRate !== 'None' && 
                defaultVatRate.trim() !== '') {
                
                // Vind de bijbehorende BTW-tariefoptie
                const vatOptions = vatRate.options;
                for (let i = 0; i < vatOptions.length; i++) {
                    if (parseFloat(vatOptions[i].value) === parseFloat(defaultVatRate)) {
                        vatRate.selectedIndex = i;
                        break;
                    }
                }
                
                // Trigger calculation update
                if (typeof calculateExclVat === 'function') {
                    calculateExclVat();
                }
            }
        });
        
        // Trigger change event if a customer is already selected on page load
        if (customerSelect.value) {
            const event = new Event('change');
            customerSelect.dispatchEvent(event);
        }
    }
}

/**
 * Set up validation for customer form
 */
function setupCustomerFormValidation() {
    const customerForm = document.getElementById('customerForm');
    const customerTypeSelect = document.getElementById('customer_type');
    
    // Regel dat BTW-nummer verplicht is voor bedrijven en leveranciers, maar niet voor particulieren
    toggleVatNumberRequired();
    
    if (customerForm) {
        customerForm.addEventListener('submit', function(event) {
            // Controleer of BTW-nummer is ingevuld voor bedrijven/leveranciers
            const customerType = customerTypeSelect ? customerTypeSelect.value : 'business';
            const vatNumber = document.getElementById('vat_number');
            
            if (vatNumber) {
                // Controleer of BTW-nummer verplicht is en ingevuld
                if ((customerType === 'business' || customerType === 'supplier') && !vatNumber.value.trim()) {
                    event.preventDefault();
                    alert('BTW-nummer is verplicht voor bedrijven en leveranciers.');
                    vatNumber.focus();
                    return;
                }
                
                // Valideer BTW-nummer formaat indien ingevuld
                if (vatNumber.value.trim()) {
                    const vatRegex = /^BE[0-9]{10}$/;
                    if (!vatRegex.test(vatNumber.value)) {
                        event.preventDefault();
                        alert('BTW-nummer moet in het formaat BE0123456789 zijn.');
                        vatNumber.focus();
                    }
                }
            }
        });
    }
}

/**
 * Toggle BTW-nummer required status based on customer type
 */
function toggleVatNumberRequired() {
    const customerTypeElement = document.getElementById('customer_type');
    const vatRequiredLabel = document.getElementById('vat_required');
    
    // Controleer of de elementen bestaan op de pagina
    if (customerTypeElement && vatRequiredLabel) {
        const customerType = customerTypeElement.value;
        if (customerType === 'business' || customerType === 'supplier') {
            vatRequiredLabel.style.display = 'inline'; // Toon sterretje
        } else {
            vatRequiredLabel.style.display = 'none'; // Verberg sterretje
        }
    }
}

/**
 * Set up VAT report period selection (quarterly/monthly)
 */
function setupVatReportPeriodSelection() {
    const quarterlyRadio = document.getElementById('quarterly');
    const monthlyRadio = document.getElementById('monthly');
    const quarterSelection = document.getElementById('quarterSelection');
    const monthSelection = document.getElementById('monthSelection');
    
    if (quarterlyRadio && monthlyRadio && quarterSelection && monthSelection) {
        // Show/hide period selection based on report type
        quarterlyRadio.addEventListener('change', function() {
            if (this.checked) {
                quarterSelection.style.display = 'block';
                monthSelection.style.display = 'none';
            }
        });
        
        monthlyRadio.addEventListener('change', function() {
            if (this.checked) {
                quarterSelection.style.display = 'none';
                monthSelection.style.display = 'block';
            }
        });
    }
}

/**
 * Handle modal deletion confirmations
 * @param {string} modalId - ID of the modal
 * @param {string} itemType - Type of item being deleted ("invoice" or "customer")
 */
function setupDeleteConfirmation(modalId, itemType) {
    const modal = document.getElementById(modalId);
    
    if (modal) {
        modal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const itemId = button.getAttribute(`data-${itemType}-id`);
            const itemName = button.getAttribute(`data-${itemType}-name`) || 
                              button.getAttribute(`data-${itemType}-number`);
            
            // Set the item name/number in the modal
            const nameElement = document.getElementById(`delete${itemType.charAt(0).toUpperCase() + itemType.slice(1)}Name`) || 
                               document.getElementById(`delete${itemType.charAt(0).toUpperCase() + itemType.slice(1)}Number`);
            
            if (nameElement) {
                nameElement.textContent = itemName;
            }
            
            // Set the form action URL
            const form = document.getElementById(`delete${itemType.charAt(0).toUpperCase() + itemType.slice(1)}Form`);
            if (form) {
                form.action = `/${itemType}s/${itemId}/delete`;
            }
            
            // Handle customer with invoices (can't delete)
            if (itemType === 'customer') {
                const hasInvoices = button.getAttribute('data-has-invoices');
                const hasInvoicesWarning = document.getElementById('hasInvoicesWarning');
                const deleteWarning = document.getElementById('deleteWarning');
                const deleteButton = document.getElementById('deleteCustomerButton');
                
                if (hasInvoicesWarning && deleteWarning && deleteButton) {
                    if (hasInvoices === 'True') {
                        hasInvoicesWarning.style.display = 'block';
                        deleteWarning.style.display = 'none';
                        deleteButton.disabled = true;
                    } else {
                        hasInvoicesWarning.style.display = 'none';
                        deleteWarning.style.display = 'block';
                        deleteButton.disabled = false;
                    }
                }
            }
        });
    }
}

/**
 * Year selector change event for reports and dashboard
 * @param {string} reportType - Type of report ("monthly", "quarterly", or "dashboard")
 */
function setupYearSelector(reportType) {
    const yearSelector = document.getElementById('yearSelector');
    
    if (yearSelector) {
        yearSelector.addEventListener('change', function() {
            const selectedYear = this.value;
            
            if (reportType === 'monthly') {
                window.location.href = `/reports/monthly/${selectedYear}`;
            } else if (reportType === 'quarterly') {
                window.location.href = `/reports/quarterly/${selectedYear}`;
            } else if (reportType === 'dashboard') {
                // For dashboard, we just reload charts via API
                loadCharts(selectedYear);
            }
        });
    }
}

/**
 * Load dashboard charts data for a specific year
 * @param {number} year - The year to load data for
 */
function loadCharts(year) {
    // Load monthly data
    fetch(`/dashboard/api/monthly-data/${year}`)
        .then(response => response.json())
        .then(data => {
            renderMonthlyChart(data);
        });
    
    // Load quarterly data
    fetch(`/dashboard/api/quarterly-data/${year}`)
        .then(response => response.json())
        .then(data => {
            renderQuarterlyChart(data);
        });
}
