import { useMemo, useState } from 'react'
import './App.css'

const BACKEND_URL = 'http://127.0.0.1:8000'

function extractResumePreview(reply) {
  const start = reply.indexOf('RESUME_PREVIEW_START')
  const end = reply.indexOf('RESUME_PREVIEW_END')
  if (start === -1 || end === -1 || end <= start) return null
  return reply.slice(start + 'RESUME_PREVIEW_START'.length, end).trim()
}

function App() {
  const [mode, setMode] = useState('form') // 'form' | 'chat'
  const [activeTab, setActiveTab] = useState('resume') // auto | resume | job_prediction
  const [sessionId] = useState(() => crypto.randomUUID())
  
  // Form state for resume builder
  const [formData, setFormData] = useState({
    full_name: '',
    education_level: '',
    skills: '',
    work_experience: '',
    career_goal: '',
  })
  
  // Chat state
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Tell me what you need: resume/CV help or job role prediction. I will ask one question at a time to collect what\'s needed.',
    },
  ])
  
  const [resumePreview, setResumePreview] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')
  const [aiResponse, setAiResponse] = useState('')

  const placeholder = useMemo(() => {
    if (activeTab === 'resume') return 'Example: Help me improve my resume'
    if (activeTab === 'job_prediction') return 'Example: Predict job roles for my skills in Nairobi'
    return 'Example: I want job prediction based on my skills and location'
  }, [activeTab])

  async function sendMessage() {
    const text = input.trim()
    if (!text || isSending) return
    setError('')
    setIsSending(true)

    setMessages((m) => [...m, { role: 'user', content: text }])
    setInput('')

    const prefix =
      activeTab === 'resume'
        ? '[RESUME_ASSISTANT] '
        : activeTab === 'job_prediction'
          ? '[JOB_PREDICTION] '
          : ''

    try {
      const resp = await fetch(`${BACKEND_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `${prefix}${text}`, session_id: sessionId }),
      })
      if (!resp.ok) throw new Error(`Backend error (${resp.status})`)
      const data = await resp.json()
      const reply = String(data.reply || '')
      setMessages((m) => [...m, { role: 'assistant', content: reply }])

      const preview = extractResumePreview(reply)
      if (preview) setResumePreview(preview)
    } catch (e) {
      setError(e?.message || 'Failed to reach backend')
    } finally {
      setIsSending(false)
    }
  }

  async function submitResumeForm() {
    if (!formData.full_name || !formData.education_level || !formData.skills || !formData.work_experience) {
      setError('Please fill in all required fields (Name, Education, Skills, Work Experience)')
      return
    }
    
    setError('')
    setIsSending(true)
    setAiResponse('')
    setResumePreview('')

    try {
      const resp = await fetch(`${BACKEND_URL}/resume/build`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          full_name: formData.full_name,
          education_level: formData.education_level,
          skills: formData.skills,
          work_experience: formData.work_experience,
          career_goal: formData.career_goal || '',
        }),
      })
      if (!resp.ok) {
        const errorText = await resp.text()
        throw new Error(`Backend error (${resp.status}): ${errorText}`)
      }
      const data = await resp.json()
      const reply = String(data.reply || '')
      const preview = String(data.preview || '')
      
      setAiResponse(reply)
      if (preview) setResumePreview(preview)
    } catch (e) {
      setError(e?.message || 'Failed to reach backend. Make sure Ollama is running.')
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="page">
      <header className="header">
        <div className="title">
          <div className="h1">AI Career Intelligence Assistant</div>
          <div className="sub">Decent Work &amp; Economic Growth</div>
        </div>
        <div className="tabs">
          <button className={activeTab === 'auto' ? 'tab active' : 'tab'} onClick={() => setActiveTab('auto')}>
            Auto
          </button>
          <button className={activeTab === 'resume' ? 'tab active' : 'tab'} onClick={() => setActiveTab('resume')}>
            Resume Builder
          </button>
          <button
            className={activeTab === 'job_prediction' ? 'tab active' : 'tab'}
            onClick={() => setActiveTab('job_prediction')}
          >
            Job Prediction
          </button>
        </div>
        <div style={{ marginTop: '10px', display: 'flex', gap: '10px' }}>
          <button
            className={mode === 'form' ? 'tab active' : 'tab'}
            onClick={() => setMode('form')}
            style={{ fontSize: '14px', padding: '6px 12px' }}
          >
            📝 Form Mode
          </button>
          <button
            className={mode === 'chat' ? 'tab active' : 'tab'}
            onClick={() => setMode('chat')}
            style={{ fontSize: '14px', padding: '6px 12px' }}
          >
            💬 Chat Mode
          </button>
        </div>
      </header>

      <main className="main">
        {mode === 'form' && activeTab === 'resume' ? (
          <section className="formSection">
            <div className="formContainer">
              <h2>Resume Builder Form</h2>
              <p style={{ color: '#666', marginBottom: '20px' }}>
                Fill in your details below. AI will generate a professional resume summary and recommendations.
              </p>
              
              <div className="formGroup">
                <label htmlFor="full_name">Full Name *</label>
                <input
                  id="full_name"
                  type="text"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  placeholder="John Doe"
                  disabled={isSending}
                />
              </div>

              <div className="formGroup">
                <label htmlFor="education_level">Education Level *</label>
                <select
                  id="education_level"
                  value={formData.education_level}
                  onChange={(e) => setFormData({ ...formData, education_level: e.target.value })}
                  disabled={isSending}
                >
                  <option value="">Select education level</option>
                  <option value="High School">High School</option>
                  <option value="Diploma">Diploma</option>
                  <option value="Bachelor's Degree">Bachelor's Degree</option>
                  <option value="Master's Degree">Master's Degree</option>
                  <option value="PhD">PhD</option>
                </select>
              </div>

              <div className="formGroup">
                <label htmlFor="skills">Skills * (comma-separated)</label>
                <input
                  id="skills"
                  type="text"
                  value={formData.skills}
                  onChange={(e) => setFormData({ ...formData, skills: e.target.value })}
                  placeholder="Python, SQL, React, Communication"
                  disabled={isSending}
                />
              </div>

              <div className="formGroup">
                <label htmlFor="work_experience">Work Experience *</label>
                <textarea
                  id="work_experience"
                  value={formData.work_experience}
                  onChange={(e) => setFormData({ ...formData, work_experience: e.target.value })}
                  placeholder="Describe your work experience (years or description)"
                  rows={4}
                  disabled={isSending}
                />
              </div>

              <div className="formGroup">
                <label htmlFor="career_goal">Career Goal (optional)</label>
                <textarea
                  id="career_goal"
                  value={formData.career_goal}
                  onChange={(e) => setFormData({ ...formData, career_goal: e.target.value })}
                  placeholder="What are your career aspirations?"
                  rows={3}
                  disabled={isSending}
                />
              </div>

              <button
                onClick={submitResumeForm}
                disabled={isSending}
                className="submitButton"
                style={{
                  width: '100%',
                  padding: '12px',
                  fontSize: '16px',
                  fontWeight: 'bold',
                  backgroundColor: '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: isSending ? 'not-allowed' : 'pointer',
                  opacity: isSending ? 0.6 : 1,
                }}
              >
                {isSending ? 'Generating Resume...' : '🚀 Generate AI Resume'}
              </button>

              {error ? <div className="error" style={{ marginTop: '15px' }}>{error}</div> : null}

              {aiResponse && (
                <div className="aiResponse" style={{ marginTop: '20px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '6px' }}>
                  <h3>AI Resume Guidance:</h3>
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{aiResponse.replace(/RESUME_PREVIEW_START[\s\S]*?RESUME_PREVIEW_END/g, '').trim()}</div>
                </div>
              )}
            </div>
          </section>
        ) : (
          <section className="chat">
            <div className="messages">
              {messages.map((m, idx) => (
                <div key={idx} className={m.role === 'user' ? 'msg user' : 'msg assistant'}>
                  <div className="bubble">{m.content}</div>
                </div>
              ))}
            </div>

            <div className="composer">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={placeholder}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') sendMessage()
                }}
                disabled={isSending}
              />
              <button onClick={sendMessage} disabled={isSending || !input.trim()}>
                Send
              </button>
            </div>
            {error ? <div className="error">{error}</div> : null}
          </section>
        )}

        <aside className="preview">
          <div className="previewHeader">Resume Preview (text-only)</div>
          <pre className="previewBody">{resumePreview || 'Preview will appear after the resume agent generates it.'}</pre>
        </aside>
      </main>
    </div>
  )
}

export default App
