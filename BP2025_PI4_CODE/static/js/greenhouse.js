$(document).ready(function() {
    console.log("Script loaded and executing");
    window.greenhouseSystems.forEach(function(systemId) {
        setupWebSocketForSystem(systemId);
    });

    setupSensorWebSocket();
    fetchData();

    $('.toggle-button').click(function(event) {
        event.preventDefault();
        var button = $(this);
        var form = button.closest('form');
        var actionUrl = form.attr('action');
        var currentAction = button.attr('data-action') === "true";
        var actionType = currentAction ? 'activate' : 'deactivate';
        var csrfToken = form.find('[name="csrfmiddlewaretoken"]').val();
        var ignoreCooldown = true;

        var systemCard = button.closest('.env-system-card');
        var slider = systemCard.find('input[type="range"]');
        var angleValue = slider.length ? slider.val() : null;

        var postData = {
            'csrfmiddlewaretoken': csrfToken,
            'action': actionType,
            'ignore_cooldown': ignoreCooldown
        };

        if (angleValue !== null) {
            postData.angle = angleValue;
        }

        $.ajax({
            type: 'POST',
            url: actionUrl,
            data: postData,
            success: function(response) {
                if (response.status === 'success') {
                    var currentActiveState = response.system_active;
                    let newAction = !currentAction;
                    button.data('action', newAction); 
                    button.attr('data-action', newAction);
                    var buttonText = currentActiveState ? 'Deactivate' : 'Activate';
                    button.text(buttonText)
                          .toggleClass('btn-success btn-warning');
                    
                    const systemId = button.attr('id').replace('toggle-button-', '');
                    const statusContainer = $(`#status-text-${systemId}`);
                    statusContainer.find('.activity-status').text(currentActiveState ? 'Active' : 'Inactive');
                    updateSystemStatus(systemId, currentActiveState, 'waiting');
                } else {
                    alert("Failed to update system status: " + response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error("AJAX error:", error);
                alert("An error occurred: " + xhr.responseText);
            }
        });
    });
});


function updateWindowAngle(angle, systemId) {
    const csrfToken = $('[name="csrfmiddlewaretoken"]').val();

    $.ajax({
        type: 'POST',
        url: `/system/${systemId}/adjust_angle/`,
        data: {
            'csrfmiddlewaretoken': csrfToken,
            'angle': angle,
        },
        success: function(response) {
            console.log('Angle updated:', response.new_angle);
            $(`#angle-display-${systemId}`).text(response.new_angle);
        },
        error: function(xhr, status, error) {
            console.error('Failed to update window angle:', xhr.responseText);
            alert('Failed to adjust window angle.');
        }
    });
}

window.updateWindowAngle = updateWindowAngle;

function fetchData() {
    $.ajax({
        url: window.location.origin + window.sensorDataUrl,
        success: function(data) {
            for (const [id, sensor] of Object.entries(data)) {
                let sensorElement = $('#sensor-' + id);
                sensorElement.find('.sensor-status').text(sensor.is_online ? 'Online' : 'Offline');
                
                let lastDataElement = sensorElement.find('.sensor-last-data');
                lastDataElement.empty();
                if (sensor.last_data) {
                    let html = '<div>';
                    for (const [key, value] of Object.entries(sensor.last_data)) {
                        html += '<span class="data-label">' + key + ':</span> ' + value + ', ';
                    }
                    html += '</div>';
                    lastDataElement.html(html);
                } else {
                    lastDataElement.html('<p>No data available</p>');
                }
            }
        },
        error: function(xhr, status, error) {
            console.error("Error fetching sensor data:", error);
        }
    });
}

function updateSystemStatus(systemId, isActive, systemStatus = "Waiting") {
    const statusText = document.querySelector(`#status-text-${systemId}`);
    const activityEl = statusText.querySelector('.activity-status');
    const statusSpan = statusText.querySelector('.system-status-span');
    const actionButton = document.querySelector(`#toggle-button-${systemId}`);

    if (!statusText || !activityEl || !statusSpan || !actionButton) {
        console.warn(`Elements for system ${systemId} not found.`);
        return;
    }

    const newAction = isActive ? "false" : "true";
    activityEl.textContent = isActive ? "Active" : "Inactive";

    let statusClass = 'text-light';
    if (systemStatus === 'waiting') statusClass = 'text-warning';
    else if (systemStatus === 'unreachable') statusClass = 'text-danger';
    else if (systemStatus === 'active') statusClass = 'text-success';

    statusSpan.textContent = capitalize(systemStatus);
    statusSpan.className = `system-status-span ${statusClass}`;

    actionButton.textContent = isActive ? "Deactivate" : "Activate";
    actionButton.classList.toggle('btn-success', !isActive);
    actionButton.classList.toggle('btn-warning', isActive);
    actionButton.setAttribute("data-action", newAction);
}

function capitalize(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function setupWebSocketForSystem(systemId) {
    var wsStart = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    var wsHost = window.location.hostname + ':8001';
    var endpoint = wsStart + wsHost + '/ws/env_system/' + systemId + '/';

    console.log("Connecting to WebSocket:", endpoint);

    var socket = new WebSocket(endpoint);

    socket.onmessage = function(e) {
        console.log("WebSocket Message Received:", e.data);

        const data = JSON.parse(e.data);
        if (data.type === 'status_update') {
            console.log(data)
            updateSystemStatus(data.system_id, data.is_active, data.status);
        }
    };

    socket.onopen = function(e) {
        console.log('WebSocket open for system ID', systemId, e);
    };

    socket.onerror = function(e) {
        console.error('WebSocket error for system ID', systemId, e);
    };

    socket.onclose = function(e) {
        console.log('WebSocket closed for system ID', systemId, e);
    };
}

function setupSensorWebSocket() {
    const wsStart = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const wsHost = window.location.hostname + ':8001';
    const endpoint = wsStart + wsHost + '/ws/sensors/';

    const socket = new WebSocket(endpoint);

    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        if (data.type === 'sensor_update') {
            console.log('Sensor update received for ID:', data.sensor_id);
            fetchData();
        }
    };

    socket.onopen = function() {
        console.log('Sensor WebSocket connection opened.');
    };

    socket.onerror = function(error) {
        console.error('Sensor WebSocket error:', error);
    };

    socket.onclose = function() {
        console.warn('Sensor WebSocket closed.');
    };
}
