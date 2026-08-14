document.addEventListener('DOMContentLoaded', function() {
    const statsUrl = '/dashboard/api/stats';
    
    fetch(statsUrl)
        .then(res => res.json())
        .then(data => {
            renderCarrerasChart(data.alumnos_por_carrera);
            renderEstadosChart('practicas', data.estados_practicas);
            renderEstadosChart('servicio', data.estados_servicio);
            renderEstadosChart('vinculacion', data.estados_vinculacion);
        })
        .catch(err => console.error('Error loading stats:', err));
    
    function getThemeColors() {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        return {
            textColor: isDark ? '#e0e0e0' : '#1a1a2e',
            gridColor: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
        };
    }
    
    function renderCarrerasChart(data) {
        const ctx = document.getElementById('chartCarreras');
        if (!ctx || !data) return;
        const colors = getThemeColors();
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: Object.keys(data),
                datasets: [{
                    label: 'Alumnos',
                    data: Object.values(data),
                    backgroundColor: [
                        'rgba(102, 126, 234, 0.8)',
                        'rgba(118, 75, 162, 0.8)',
                        'rgba(52, 199, 89, 0.8)',
                        'rgba(255, 149, 0, 0.8)',
                        'rgba(255, 59, 48, 0.8)',
                    ],
                    borderRadius: 8,
                    borderSkipped: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: 'Alumnos por Carrera', color: colors.textColor, font: { size: 16, weight: '600' } }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: colors.gridColor }, ticks: { color: colors.textColor } },
                    x: { grid: { display: false }, ticks: { color: colors.textColor } }
                }
            }
        });
    }
    
    function renderEstadosChart(moduleId, data) {
        const ctx = document.getElementById('chart-' + moduleId);
        if (!ctx || !data) return;
        const colors = getThemeColors();
        
        const estadoColors = {
            'Pendiente': 'rgba(255, 204, 0, 0.8)',
            'Entregado': 'rgba(52, 199, 89, 0.8)',
            'Recibido': 'rgba(0, 122, 255, 0.8)',
            'No Realizado': 'rgba(255, 59, 48, 0.8)'
        };
        
        const moduleLabels = {
            'practicas': 'Prácticas Profesionales',
            'servicio': 'Servicio Social',
            'vinculacion': 'Vinculación'
        };
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(data),
                datasets: [{
                    data: Object.values(data),
                    backgroundColor: Object.keys(data).map(k => estadoColors[k] || 'rgba(128,128,128,0.8)'),
                    borderWidth: 0,
                    spacing: 4,
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: colors.textColor, padding: 16, usePointStyle: true } },
                    title: { display: true, text: moduleLabels[moduleId] || moduleId, color: colors.textColor, font: { size: 16, weight: '600' } }
                }
            }
        });
    }
});
