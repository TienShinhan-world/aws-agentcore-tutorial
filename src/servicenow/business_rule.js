/**
 * ServiceNow Business Rule Script for AWS AgentCore Integration
 *
 * This script triggers when incidents are created or updated in ServiceNow
 * and sends the ticket data to AWS AgentCore via API Gateway webhook.
 *
 * INSTALLATION INSTRUCTIONS:
 * ==========================
 * 1. Navigate to: System Definition > Business Rules
 * 2. Click "New" to create a new Business Rule
 * 3. Configure as follows:
 *    - Name: AWS-AgentCore Webhook-SendIncident
 *    - Table: incident
 *    - Active: true
 *    - Advanced: true (check this box)
 *    - When to run:
 *      - When: after
 *      - Insert: true
 *      - Update: true (optional - for updates)
 *    - Filter Conditions (optional):
 *      - Priority is one of: 1 - Critical, 2 - High
 *      - State is: 1 - New
 * 4. Copy this script into the "Script" field
 * 5. Click "Submit"
 *
 * PREREQUISITES:
 * ==============
 * 1. Create a REST Message named "AWS AgentCore Webhook"
 *    - Navigate to: System Web Services > Outbound > REST Message
 *    - Create new with:
 *      - Name: AWS-AgentCore-Webhook
 *      - Endpoint: https://YOUR_API_GATEWAY_URL/webhook/servicenow
 *    - Add HTTP Method:
 *      - Name: SendIncident
 *      - HTTP Method: POST
 *      - Endpoint: (same as above)
 *      - HTTP Headers:
 *        - Content-Type: application/json
 *        - x-api-key: <copy paste your api key here>
 *      - HTTP Request Body: (see PAYLOAD_TEMPLATE below)
 *
 *
 * PAYLOAD_TEMPLATE for REST Message HTTP Request:
 * ================================================
 * {
 *   "number": "${number}",
 *   "sys_id": "${sys_id}",
 *   "short_description": "${short_description}",
 *   "description": "${description}",
 *   "urgency": "${urgency}",
 *   "impact": "${impact}",
 *   "priority": "${priority}",
 *   "state": "${state}",
 *   "category": "${category}",
 *   "subcategory": "${subcategory}",
 *   "assignment_group": "${assignment_group}",
 *   "assigned_to": "${assigned_to}",
 *   "caller_id": "${caller_id}",
 *   "sys_created_on": "${sys_created_on}",
 *   "sys_updated_on": "${sys_updated_on}"
 * }
 */

(function executeRule(current, previous /*null when async*/) {

    // Configuration
    var REST_MESSAGE_NAME = 'AWS-AgentCore-Webhook';
    var HTTP_METHOD_NAME = 'SendIncident';
    var API_KEY_PROPERTY = 'aws.agentcore.api_key';

    // ============================================================
    // LOOP PREVENTION - Critical to avoid infinite webhook loops!
    // ============================================================

    // 1. Skip if this is an update by the integration user (agent)
    //    Change 'agentcore_integration' to your ServiceNow integration username
    var INTEGRATION_USER = 'agentcore_integration';
    if (gs.getUserName() == INTEGRATION_USER) {
        gs.debug('AWS AgentCore: Skipping webhook - update by integration user');
        return;
    }

    // 2. For updates, only trigger on meaningful changes (not work_notes)
    if (current.operation() == 'update') {
        // Check if only work_notes or comments changed - if so, skip
        var meaningfulChange = current.short_description.changes() ||
                               current.description.changes() ||
                               current.state.changes() ||
                               current.priority.changes() ||
                               current.urgency.changes() ||
                               current.impact.changes() ||
                               current.category.changes() ||
                               current.assigned_to.changes() ||
                               current.assignment_group.changes();

        if (!meaningfulChange) {
            gs.debug('AWS AgentCore: Skipping webhook - no meaningful field changes');
            return;
        }

        // 3. Skip if state is not "New" (1) - agent already processed
        if (current.getValue('state') != '1') {
            gs.debug('AWS AgentCore: Skipping webhook - ticket not in New state (state=' + current.getValue('state') + ')');
            return;
        }
    }

    // 4. Additional safety: check for recent agent work notes (within last 60 seconds)
    //    This prevents re-triggering if webhook was already sent recently
    var recentWorkNotes = current.work_notes.getJournalEntry(1);
    if (recentWorkNotes && recentWorkNotes.indexOf('[AI Agent Analysis]') > -1) {
        gs.debug('AWS AgentCore: Skipping webhook - recent AI agent work notes detected');
        return;
    }

    gs.info('AWS AgentCore: Processing webhook for ' + current.getValue('number') + ' (operation: ' + current.operation() + ')');

    try {
        // Create REST Message reference
        var restMessage = new sn_ws.RESTMessageV2(REST_MESSAGE_NAME, HTTP_METHOD_NAME);

        // Set API Key from system property
        var apiKey = gs.getProperty(API_KEY_PROPERTY);
        if (!apiKey) {
            gs.error('AWS AgentCore: API key not configured. Set property: ' + API_KEY_PROPERTY);
            return;
        }
        restMessage.setStringParameter('api_key', apiKey);

        // Set all incident field variables (for REST Message template substitution)
        restMessage.setStringParameterNoEscape('number', current.getValue('number') || '');
        restMessage.setStringParameterNoEscape('sys_id', current.getValue('sys_id') || '');
        restMessage.setStringParameterNoEscape('short_description', current.getValue('short_description') || '');
        restMessage.setStringParameterNoEscape('description', current.getValue('description') || '');
        restMessage.setStringParameterNoEscape('urgency', current.getValue('urgency') || '3');
        restMessage.setStringParameterNoEscape('impact', current.getValue('impact') || '3');
        restMessage.setStringParameterNoEscape('priority', current.getValue('priority') || '4');
        restMessage.setStringParameterNoEscape('state', current.getValue('state') || '1');
        restMessage.setStringParameterNoEscape('category', current.getValue('category') || '');
        restMessage.setStringParameterNoEscape('subcategory', current.getValue('subcategory') || '');

        // Get display values for reference fields (shows name instead of sys_id)
        restMessage.setStringParameterNoEscape('assignment_group', current.getDisplayValue('assignment_group') || '');
        restMessage.setStringParameterNoEscape('assigned_to', current.getDisplayValue('assigned_to') || '');
        restMessage.setStringParameterNoEscape('caller_id', current.getDisplayValue('caller_id') || '');

        // Timestamps
        restMessage.setStringParameterNoEscape('sys_created_on', current.getValue('sys_created_on') || '');
        restMessage.setStringParameterNoEscape('sys_updated_on', current.getValue('sys_updated_on') || '');

        // Set correlation ID for tracking
        restMessage.setEccCorrelator(current.getValue('number'));

        // Execute asynchronously to avoid blocking ServiceNow transaction
        // For synchronous execution, use: var response = restMessage.execute();
        var response = restMessage.executeAsync();

        // Log success
        gs.info('AWS AgentCore: Webhook triggered for incident ' + current.getValue('number'));

    } catch (ex) {
        // Log error but don't block the ServiceNow transaction
        gs.error('AWS AgentCore: Webhook error for incident ' + current.getValue('number') + ': ' + ex.getMessage());
    }

})(current, previous);


/**
 * ALTERNATIVE: Synchronous version with response handling
 * ========================================================
 * Use this version if you need to process the agent's response
 * directly in ServiceNow (e.g., auto-populate work notes).
 *
 * WARNING: Synchronous calls may slow down the ServiceNow UI.
 * Only use for low-volume, high-priority scenarios.
 */

/*
(function executeRule(current, previous) {

    var REST_MESSAGE_NAME = 'AWS AgentCore Webhook';
    var HTTP_METHOD_NAME = 'POST Incident';
    var API_KEY_PROPERTY = 'aws.agentcore.api_key';

    try {
        var restMessage = new sn_ws.RESTMessageV2(REST_MESSAGE_NAME, HTTP_METHOD_NAME);

        var apiKey = gs.getProperty(API_KEY_PROPERTY);
        if (!apiKey) {
            gs.error('AWS AgentCore: API key not configured');
            return;
        }
        restMessage.setStringParameter('api_key', apiKey);

        // Set parameters (same as async version above)
        restMessage.setStringParameterNoEscape('number', current.getValue('number') || '');
        restMessage.setStringParameterNoEscape('sys_id', current.getValue('sys_id') || '');
        restMessage.setStringParameterNoEscape('short_description', current.getValue('short_description') || '');
        restMessage.setStringParameterNoEscape('description', current.getValue('description') || '');
        restMessage.setStringParameterNoEscape('urgency', current.getValue('urgency') || '3');
        restMessage.setStringParameterNoEscape('impact', current.getValue('impact') || '3');
        restMessage.setStringParameterNoEscape('priority', current.getValue('priority') || '4');
        restMessage.setStringParameterNoEscape('state', current.getValue('state') || '1');
        restMessage.setStringParameterNoEscape('category', current.getValue('category') || '');
        restMessage.setStringParameterNoEscape('subcategory', current.getValue('subcategory') || '');
        restMessage.setStringParameterNoEscape('assignment_group', current.getDisplayValue('assignment_group') || '');
        restMessage.setStringParameterNoEscape('assigned_to', current.getDisplayValue('assigned_to') || '');
        restMessage.setStringParameterNoEscape('caller_id', current.getDisplayValue('caller_id') || '');
        restMessage.setStringParameterNoEscape('sys_created_on', current.getValue('sys_created_on') || '');
        restMessage.setStringParameterNoEscape('sys_updated_on', current.getValue('sys_updated_on') || '');

        // Execute synchronously
        var response = restMessage.execute();
        var httpStatus = response.getStatusCode();
        var responseBody = response.getBody();

        if (httpStatus == 200) {
            // Parse response and update ticket with agent analysis
            var result = JSON.parse(responseBody);
            if (result.success && result.analysis) {
                // Add agent analysis as work note
                current.work_notes = '[AI Agent Analysis]\n\n' + result.analysis;
                current.state = '2'; // In Progress
                current.update();
                gs.info('AWS AgentCore: Updated incident ' + current.getValue('number') + ' with agent analysis');
            }
        } else {
            gs.error('AWS AgentCore: Webhook failed with status ' + httpStatus + ': ' + responseBody);
        }

    } catch (ex) {
        gs.error('AWS AgentCore: Webhook error: ' + ex.getMessage());
    }

})(current, previous);
*/
