/**
 * Charts JavaScript file for Facturatie & Boekhouding application
 * Uses Chart.js for rendering financial charts
 */

// Chart variables for later destruction
let monthlyChart = null;
let quarterlyChart = null;
let vatChart = null;

/**
 * Render monthly income/expense chart
 * @param {Object} data - Chart data with labels, income, expenses and profit arrays
 */
function renderMonthlyChart(data) {
    const ctx = document.getElementById('monthlyChart');
    if (!ctx) return;
    
    // Get the context
    const context = ctx.getContext('2d');
    
    // Destroy previous chart if exists
    if (monthlyChart) {
        monthlyChart.destroy();
    }
    
    // Create new chart
    monthlyChart = new Chart(context, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'Inkomsten',
                    data: data.income,
                    backgroundColor: 'rgba(40, 167, 69, 0.7)',
                    borderColor: 'rgba(40, 167, 69, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Uitgaven',
                    data: data.expenses,
                    backgroundColor: 'rgba(220, 53, 69, 0.7)',
                    borderColor: 'rgba(220, 53, 69, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Winst',
                    data: data.profit,
                    type: 'line',
                    fill: false,
                    borderColor: 'rgba(23, 162, 184, 1)',
                    tension: 0.1,
                    borderWidth: 2
                }
            ]
        },
        options: {
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += new Intl.NumberFormat('nl-BE', { 
                                    style: 'currency', 
                                    currency: 'EUR' 
                                }).format(context.parsed.y);
                            }
                            return label;
                        }
                    }
                }
            },
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '€' + value.toLocaleString('nl-BE');
                        }
                    }
                }
            }
        }
    });
}

/**
 * Render quarterly income/expense chart
 * @param {Object} data - Chart data with labels, income, expenses and profit arrays
 */
function renderQuarterlyChart(data) {
    const ctx = document.getElementById('quarterlyChart');
    if (!ctx) return;
    
    // Get the context
    const context = ctx.getContext('2d');
    
    // Destroy previous chart if exists
    if (quarterlyChart) {
        quarterlyChart.destroy();
    }
    
    // Create new chart
    quarterlyChart = new Chart(context, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'Inkomsten',
                    data: data.income,
                    backgroundColor: 'rgba(40, 167, 69, 0.7)',
                    borderColor: 'rgba(40, 167, 69, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Uitgaven',
                    data: data.expenses,
                    backgroundColor: 'rgba(220, 53, 69, 0.7)',
                    borderColor: 'rgba(220, 53, 69, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Winst',
                    data: data.profit,
                    type: 'line',
                    fill: false,
                    borderColor: 'rgba(23, 162, 184, 1)',
                    tension: 0.1,
                    borderWidth: 2
                }
            ]
        },
        options: {
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += new Intl.NumberFormat('nl-BE', { 
                                    style: 'currency', 
                                    currency: 'EUR' 
                                }).format(context.parsed.y);
                            }
                            return label;
                        }
                    }
                }
            },
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '€' + value.toLocaleString('nl-BE');
                        }
                    }
                }
            }
        }
    });
}

/**
 * Render VAT report chart
 * @param {number} grid54 - Output VAT amount
 * @param {number} grid59 - Input VAT amount
 * @param {number} grid71 - VAT balance
 * @param {string} periodName - Name of the period (e.g., "Q1 2023")
 */
function renderVatChart(grid54, grid59, grid71, periodName) {
    const ctx = document.getElementById('vatChart');
    if (!ctx) return;
    
    // Get the context
    const context = ctx.getContext('2d');
    
    // Destroy previous chart if exists
    if (vatChart) {
        vatChart.destroy();
    }
    
    // Create new chart
    vatChart = new Chart(context, {
        type: 'bar',
        data: {
            labels: [`BTW-aangifte voor ${periodName}`],
            datasets: [
                {
                    label: 'Verschuldigde BTW (rooster 54)',
                    data: [grid54],
                    backgroundColor: 'rgba(220, 53, 69, 0.7)',
                    borderColor: 'rgba(220, 53, 69, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Aftrekbare BTW (rooster 59)',
                    data: [grid59],
                    backgroundColor: 'rgba(40, 167, 69, 0.7)',
                    borderColor: 'rgba(40, 167, 69, 1)',
                    borderWidth: 1
                },
                {
                    label: 'BTW Saldo (rooster 71)',
                    data: [grid71],
                    backgroundColor: 'rgba(23, 162, 184, 0.7)',
                    borderColor: 'rgba(23, 162, 184, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += new Intl.NumberFormat('nl-BE', { 
                                    style: 'currency', 
                                    currency: 'EUR' 
                                }).format(context.parsed.y);
                            }
                            return label;
                        }
                    }
                }
            },
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '€' + value.toLocaleString('nl-BE');
                        }
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 0
                    }
                }
            }
        }
    });
}

/**
 * Render customer report chart
 * @param {Array} labels - Customer names
 * @param {Array} income - Income values by customer
 * @param {Array} vatCollected - VAT collected values by customer 
 */
function renderCustomerChart(labels, income, vatCollected) {
    const ctx = document.getElementById('customerChart');
    if (!ctx) return;
    
    // Get the context
    const context = ctx.getContext('2d');
    
    // Create chart
    new Chart(context, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Inkomsten (excl. BTW)',
                    data: income,
                    backgroundColor: 'rgba(40, 167, 69, 0.7)',
                    borderColor: 'rgba(40, 167, 69, 1)',
                    borderWidth: 1
                },
                {
                    label: 'BTW geïnd',
                    data: vatCollected,
                    backgroundColor: 'rgba(23, 162, 184, 0.7)',
                    borderColor: 'rgba(23, 162, 184, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            indexAxis: 'y',
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.x !== null) {
                                label += new Intl.NumberFormat('nl-BE', { 
                                    style: 'currency', 
                                    currency: 'EUR' 
                                }).format(context.parsed.x);
                            }
                            return label;
                        }
                    }
                }
            },
            responsive: true,
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '€' + value.toLocaleString('nl-BE');
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create a doughnut chart for income vs expenses
 * @param {number} income - Total income
 * @param {number} expenses - Total expenses
 */
function renderIncomeExpenseDoughnutChart(income, expenses) {
    const ctx = document.getElementById('incomeExpenseChart');
    if (!ctx) return;
    
    // Get the context
    const context = ctx.getContext('2d');
    
    // Create chart
    new Chart(context, {
        type: 'doughnut',
        data: {
            labels: ['Inkomsten', 'Uitgaven'],
            datasets: [{
                data: [income, expenses],
                backgroundColor: [
                    'rgba(40, 167, 69, 0.7)',
                    'rgba(220, 53, 69, 0.7)'
                ],
                borderColor: [
                    'rgba(40, 167, 69, 1)',
                    'rgba(220, 53, 69, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed !== null) {
                                label += new Intl.NumberFormat('nl-BE', { 
                                    style: 'currency', 
                                    currency: 'EUR' 
                                }).format(context.parsed);
                            }
                            return label;
                        }
                    }
                }
            }
        }
    });
}
