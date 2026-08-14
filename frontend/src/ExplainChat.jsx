import { useState } from 'react'
import { API_URL } from './config.js'
import './ExplainChat.css'

/**
 * Chat box for asking follow-up questions about a specific prediction.
 * Grounded server-side (see backend/main.py's build_system_instruction) —
 * every reply is tied to this patient's actual top_factors, not free-form.
 */
function ExplainChat({ predictionType, riskScore, topFactors }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [interactionId, setInteractionId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSend(event) {
    event.preventDefault()
    if (!input.trim()) return

    const userMessage = input
    setMessages((prev) => [...prev, { role: 'user', text: userMessage }])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_URL}/explain-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prediction_type: predictionType,
          risk_score: riskScore,
          top_factors: topFactors,
          message: userMessage,
          previous_interaction_id: interactionId,
        }),
      })

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`)
      }

      const data = await response.json()
      setMessages((prev) => [...prev, { role: 'assistant', text: data.reply }])
      setInteractionId(data.interaction_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="explain-chat">
      <p className="explain-chat-label">Ask about this prediction</p>

      {messages.length > 0 && (
        <div className="explain-chat-history">
          {messages.map((msg, i) => (
            <div key={i} className={`explain-chat-message ${msg.role}`}>
              {msg.text}
            </div>
          ))}
          {loading && <div className="explain-chat-message assistant loading">Thinking…</div>}
        </div>
      )}

      {error && <p className="explain-chat-error">Error: {error}</p>}

      <form className="explain-chat-input-row" onSubmit={handleSend}>
        <input
          type="text"
          placeholder="e.g. Why is this patient high risk?"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>Ask</button>
      </form>
    </div>
  )
}

export default ExplainChat
