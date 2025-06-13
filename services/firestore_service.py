from google.cloud import firestore

db = firestore.Client()

def obtener_historial(numero_usuario, max_turnos=10):
    doc_ref = db.collection('conversaciones').document(numero_usuario)
    doc = doc_ref.get()

    if doc.exists:
        historial = doc.to_dict().get("historial", [])
        return historial[-max_turnos:]
    else:
        return []

def guardar_interaccion(numero_usuario, user_msg, bot_msg):
    doc_ref = db.collection('conversaciones').document(numero_usuario)
    historial = obtener_historial(numero_usuario)

    historial.append({"role": "user", "content": user_msg})
    historial.append({"role": "assistant", "content": bot_msg})

    doc_ref.set({"historial": historial})
