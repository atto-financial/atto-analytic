document.addEventListener('DOMContentLoaded', function () {
    // Chart for Loan Request Status Distribution (Pie Chart - existing)
    fetch('/api/loan_request_status_data')
        .then(response => response.json())
        .then(data => {
            const ctx = document.getElementById('loanRequestStatusChart').getContext('2d');
            new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Number of Loan Requests',
                        data: data.data,
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.8)', 'rgba(54, 162, 235, 0.8)',
                            'rgba(255, 206, 86, 0.8)', 'rgba(75, 192, 192, 0.8)',
                            'rgba(153, 102, 255, 0.8)', 'rgba(255, 159, 64, 0.8)'
                        ],
                        borderColor: [
                            'rgba(255, 99, 132, 1)', 'rgba(54, 162, 235, 1)',
                            'rgba(255, 206, 86, 1)', 'rgba(75, 192, 192, 1)',
                            'rgba(153, 102, 255, 1)', 'rgba(255, 159, 64, 1)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { display: true, position: 'right' },
                        title: { display: true, text: 'Loan Request Status Distribution' }
                    }
                }
            });
        })
        .catch(error => console.error('Error fetching loan request status data:', error));

    // Combined Chart: Daily Loan Lent vs. Payoff Amount (Paired Bar Chart - existing)
    fetch('/api/daily_loan_transaction_summary')
        .then(response => response.json())
        .then(data => {
            const labels = data.map(item => item.transaction_date);
            const lentAmounts = data.map(item => item.total_lent_amount);
            const payoffAmounts = data.map(item => item.total_payoff_amount);

            const ctxSummary = document.getElementById('dailyLoanSummaryChart').getContext('2d');
            new Chart(ctxSummary, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Loan Lent Amount',
                            data: lentAmounts,
                            backgroundColor: 'rgba(255, 159, 64, 0.7)', // Orange
                            borderColor: 'rgba(255, 159, 64, 1)',
                            borderWidth: 1,
                            borderRadius: 5
                        },
                        {
                            label: 'Payoff Amount',
                            data: payoffAmounts,
                            backgroundColor: 'rgba(75, 192, 192, 0.7)', // Blue
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 1,
                            borderRadius: 5
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: { unit: 'day', tooltipFormat: 'MMM D, YYYY', displayFormats: { day: 'MMM D' } },
                            title: { display: true, text: 'Date' },
                            offset: true,
                            grid: { offset: true },
                            barPercentage: 0.8,
                            categoryPercentage: 0.8
                        },
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Amount' }
                        }
                    },
                    plugins: {
                        legend: { display: true },
                        title: { display: true, text: 'Daily Loan Lent vs. Payoff Amount' }
                    }
                }
            });

            // Daily Net Loan Flow (Payoff - Lent) (existing - no changes)
            const netAmounts = data.map(item => item.total_payoff_amount - item.total_lent_amount);

            const ctxNetFlow = document.getElementById('dailyNetLoanFlowChart').getContext('2d');
            new Chart(ctxNetFlow, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Net Loan Flow (Payoff - Lent)',
                        data: netAmounts,
                        backgroundColor: (context) => {
                            const value = context.raw;
                            if (value >= 0) { return 'rgba(40, 161, 167, 0.4)'; } else { return 'rgba(220, 148, 53, 0.4)'; }
                        },
                        borderColor: (context) => {
                            const value = context.raw;
                            if (value >= 0) { return 'rgba(40, 123, 167, 1)'; } else { return 'rgba(220, 109, 53, 1)'; }
                        },
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { type: 'time', time: { unit: 'day', tooltipFormat: 'MMM D, YYYY', displayFormats: { day: 'MMM D' } }, title: { display: true, text: 'Date' } },
                        y: { beginAtZero: false, title: { display: true, text: 'Net Amount' } }
                    },
                    plugins: {
                        legend: { display: true },
                        title: { display: true, text: 'Daily Net Loan Flow (Payoff - Lent)' }
                    }
                }
            });
        })
        .catch(error => console.error('Error fetching daily loan transaction summary data for net flow:', error));

    // Chart: Daily Payoff Components
    fetch('/api/daily_payoff_details')
        .then(response => response.json())
        .then(data => {
            const labels = data.map(item => item.payoff_date);
            const principal = data.map(item => item.total_principal_paid);
            const interest = data.map(item => item.total_interest_paid);
            const initialFee = data.map(item => item.total_initial_fee_paid);
            const fineAmount = data.map(item => item.total_fine_amount_paid);
            const collectionFee = data.map(item => item.total_collection_fee_paid);
            // NEW: Extract total_actual_payoff_from_action for the line chart
            const actualPayoffFromAction = data.map(item => item.total_actual_payoff_from_action);

            // Calculate total sums for each component and display them (existing code)
            let totalPrincipal = 0;
            let totalInterest = 0;
            let totalInitialFee = 0;
            let totalFineAmount = 0;
            let totalCollectionFee = 0;

            data.forEach(item => {
                totalPrincipal += item.total_principal_paid || 0;
                totalInterest += item.total_interest_paid || 0;
                totalInitialFee += item.total_initial_fee_paid || 0;
                totalFineAmount += item.total_fine_amount_paid || 0;
                totalCollectionFee += item.total_collection_fee_paid || 0;
            });

            const summaryDiv = document.getElementById('payoffComponentsSummary');
            if (summaryDiv) {
                summaryDiv.innerHTML = `
                <h3>Overall Payoff Components Summary:</h3>
                <ul>
                    <li>Principal Paid: <span>฿${totalPrincipal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></li>
                    <li>Interest Paid: <span>฿${totalInterest.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></li>
                    <li>Initial Fee Paid: <span>฿${totalInitialFee.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></li>
                    <li>Fine Amount Paid: <span>฿${totalFineAmount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></li>
                    <li>Collection Fee Paid: <span>฿${totalCollectionFee.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></li>
                </ul>
                `;
            }

            const ctx = document.getElementById('dailyPayoffDetailsChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar', // The base type is still 'bar' for the stacked components
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Principal Paid',
                            data: principal,
                            backgroundColor: 'rgba(1, 38, 77,0.7)',
                            borderColor: 'rgba(1, 38, 77,1)',
                            borderWidth: 1,
                            stack: 'payoffComponents' // All bar datasets go into this stack
                        },
                        {
                            label: 'Interest Paid',
                            data: interest,
                            backgroundColor: 'rgba(255, 193, 7, 0.7)',
                            borderColor: 'rgba(255, 193, 7, 1)',
                            borderWidth: 1,
                            stack: 'payoffComponents'
                        },
                        {
                            label: 'Initial Fee Paid',
                            data: initialFee,
                            backgroundColor: 'rgba(40, 167, 69, 0.7)',
                            borderColor: 'rgba(40, 167, 69, 1)',
                            borderWidth: 1,
                            stack: 'payoffComponents'
                        },
                        {
                            label: 'Fine Amount Paid',
                            data: fineAmount,
                            backgroundColor: 'rgba(220, 53, 69, 0.7)',
                            borderColor: 'rgba(220, 53, 69, 1)',
                            borderWidth: 1,
                            stack: 'payoffComponents'
                        },
                        {
                            label: 'Collection Fee Paid',
                            data: collectionFee,
                            backgroundColor: 'rgba(108, 117, 125, 0.7)',
                            borderColor: 'rgba(108, 117, 125, 1)',
                            borderWidth: 1,
                            stack: 'payoffComponents'
                        },
                        {
                            // NEW DATASET: Actual Payoff Amount as a line
                            label: 'Actual Payoff (from Action History)',
                            data: actualPayoffFromAction,
                            type: 'line', // This makes it a line chart within the bar chart
                            borderColor: 'rgba(128, 0, 128, 1)', // Distinct color (e.g., Purple)
                            backgroundColor: 'rgba(128, 0, 128, 0.2)', // Light fill for the line
                            borderWidth: 3,
                            fill: false, // Do not fill the area under the line
                            pointRadius: 4, // Size of the points on the line
                            pointBackgroundColor: 'rgba(128, 0, 128, 1)',
                            yAxisID: 'y' // Use the same Y-axis as the bars for direct comparison
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: { unit: 'day', tooltipFormat: 'MMM D, YYYY', displayFormats: { day: 'MMM D' } },
                            title: { display: true, text: 'Date' }
                        },
                        y: {
                            stacked: true, // Keep the bar datasets stacked
                            beginAtZero: true,
                            title: { display: true, text: 'Amount' }
                        }
                    },
                    plugins: {
                        legend: { display: true },
                        title: { display: true, text: 'Daily Payoff Components & Actual Payoff' } // Updated chart title
                    }
                }
            });
        })
        .catch(error => console.error('Error fetching daily payoff details data:', error));

});