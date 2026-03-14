// ── Pin ────
const int PIN_FLAME  = 7;
const int PIN_RELAY  = 8;
const int PIN_BUZZER = 9;
const int PIN_TRIG   = 10;
const int PIN_ECHO   = 11;
const int PIN_LED    = 13;

// ── Serial ───
String inputString    = "";
bool   stringComplete = false;

void setup() {
  Serial.begin(9600);
  inputString.reserve(64);

  pinMode(PIN_LED,    OUTPUT);
  pinMode(PIN_FLAME,  INPUT);
  pinMode(PIN_RELAY,  OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_TRIG,   OUTPUT);
  pinMode(PIN_ECHO,   INPUT);

  digitalWrite(PIN_RELAY,  HIGH);  // solenoid tutup (active LOW)
  digitalWrite(PIN_BUZZER, HIGH);  // buzzer mati   (active LOW)
  digitalWrite(PIN_LED,    LOW);

  for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_LED, HIGH); delay(200);
    digitalWrite(PIN_LED, LOW);  delay(200);
  }
}

float bacaJarak() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  long dur = pulseIn(PIN_ECHO, HIGH, 30000);
  return (dur == 0) ? 9999.0 : dur * 0.034 / 2.0;
}

// Format CSV: DATA,<jarak>,<api>,<relay>,<buzzer>
void kirimData() {
  float jarak       = bacaJarak();
  int   api         = (digitalRead(PIN_FLAME) == LOW) ? 1 : 0;
  int   relayState  = digitalRead(PIN_RELAY);
  int   buzzerState = digitalRead(PIN_BUZZER);

  Serial.print("DATA,");
  Serial.print(jarak, 2);
  Serial.print(",");
  Serial.print(api);
  Serial.print(",");
  Serial.print(relayState);
  Serial.print(",");
  Serial.println(buzzerState);

  digitalWrite(PIN_LED, HIGH); delay(10); digitalWrite(PIN_LED, LOW);
}

// Format: CMD:device,state\n
void prosesPerintah(String cmd) {
  int comma = cmd.indexOf(',');
  if (comma == -1) return;

  String device = cmd.substring(0, comma);
  int    state  = cmd.substring(comma + 1).toInt();

  if (device == "relay") {
    digitalWrite(PIN_RELAY, !state);
  } else if (device == "buzzer") {
    digitalWrite(PIN_BUZZER, !state);
  } else if (device == "status") {
    kirimData();
    return;
  }

  Serial.print("ACK:"); Serial.println(cmd);
}

void loop() {
  static unsigned long lastSend = 0;
  if (millis() - lastSend > 1000) {
    lastSend = millis();
    kirimData();
  }

  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') stringComplete = true;
    else           inputString   += c;
  }

  if (stringComplete) {
    if (inputString.startsWith("CMD:")) {
      prosesPerintah(inputString.substring(4));
    }
    inputString    = "";
    stringComplete = false;
  }
}
