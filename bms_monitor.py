# ─── BMS Disconnect Notification ─────────────────────────────────────────────
- alias: "BMS Disconnected Alert"
  description: "Notify phone and Telegram when BMS loses connection"
  trigger:
    - platform: mqtt
      topic: "pacebms/bms_error"
  condition:
    - condition: template
      value_template: "{{ (trigger.payload_json.status | default('')) == 'disconnected' }}"
  action:
    - action: notify.mobile_app_s25_ultra
      data:
        title: "⚠️ BMS Disconnected"
        message: >
          Hubble BMS Disconnected!
          Offline for: {{ trigger.payload_json.offline_time }}
          Retry attempt: {{ trigger.payload_json.retry_count }}
    - action: notify.send_message
      target:
        entity_id: notify.telegram
      data:
        message: >
          ⚠️ Hubble BMS Disconnected!
          Offline for: {{ trigger.payload_json.offline_time }}
          Retry attempt: {{ trigger.payload_json.retry_count }}

# ─── BMS Recovery Notification ───────────────────────────────────────────────
- alias: "BMS Recovered Alert"
  description: "Notify phone and Telegram when BMS reconnects"
  trigger:
    - platform: mqtt
      topic: "pacebms/bms_error"
  condition:
    - condition: template
      value_template: "{{ (trigger.payload_json.status | default('')) == 'recovered' }}"
  action:
    - action: notify.mobile_app_s25_ultra
      data:
        title: "✅ BMS Reconnected"
        message: >
          Hubble BMS Reconnected!
          Was offline for: {{ trigger.payload_json.offline_time }}
          Took {{ trigger.payload_json.retry_count }} retries to recover
    - action: notify.send_message
      target:
        entity_id: notify.telegram
      data:
        message: >
          ✅ Hubble BMS Reconnected!
          Was offline for: {{ trigger.payload_json.offline_time }}
          Took {{ trigger.payload_json.retry_count }} retries to recover

# ─── BMS Startup Notification ─────────────────────────────────────────────────
- alias: "BMS Started Alert"
  description: "Notify Telegram when BMS monitor starts up"
  trigger:
    - platform: mqtt
      topic: "pacebms/bms_status"
  condition:
    - condition: template
      value_template: "{{ (trigger.payload_json.status | default('')) == 'startup' }}"
  action:
    - action: notify.mobile_app_s25_ultra
      data:
        title: "🟢 BMS Monitor Started"
        message: >
          Hubble BMS Monitor Started!
          BMS Serial: {{ trigger.payload_json.bms_sn }}
          Version: {{ trigger.payload_json.bms_version }}
    - action: notify.send_message
      target:
        entity_id: notify.telegram
      data:
        message: >
          🟢 Hubble BMS Monitor Started!
          BMS Serial: {{ trigger.payload_json.bms_sn }}
          Version: {{ trigger.payload_json.bms_version }}

# ─── BMS Shutdown Notification ────────────────────────────────────────────────
- alias: "BMS Shutdown Alert"
  description: "Notify Telegram when BMS monitor shuts down"
  trigger:
    - platform: mqtt
      topic: "pacebms/bms_status"
  condition:
    - condition: template
      value_template: "{{ (trigger.payload_json.status | default('')) == 'shutdown' }}"
  action:
    - action: notify.mobile_app_s25_ultra
      data:
        title: "🔴 BMS Monitor Stopped"
        message: >
          Hubble BMS Monitor has stopped.
          BMS Serial: {{ trigger.payload_json.bms_sn }}
    - action: notify.send_message
      target:
        entity_id: notify.telegram
      data:
        message: >
          🔴 Hubble BMS Monitor has stopped.
          BMS Serial: {{ trigger.payload_json.bms_sn }}