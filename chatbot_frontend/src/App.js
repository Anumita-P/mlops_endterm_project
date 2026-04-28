import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader, AlertCircle, CheckCircle2, TrendingUp } from 'lucide-react';

export default function AgriculturalChatbot() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      text: '🌾 नमस्कार! Welcome to Krishi Sahaya - your agricultural advisor. Tell me about your crop and current challenges.',
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [district, setDistrict] = useState('Thanjavur');
  const [crop, setCrop] = useState('rice');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    // Add user message
    const userMessage = {
      id: messages.length + 1,
      type: 'user',
      text: inputValue,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    try {
      // Call FastAPI backend
      const response = await fetch('http://localhost:8001/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          farmer_id: `farmer_${Date.now()}`,
          district,
          crop,
          query: inputValue,
          weather_context: {
            temp: 32,
            rainfall: 100,
            humidity: 75,
            wind_speed: 5
          }
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(JSON.stringify(errorData));
      }
      
      const data = await response.json();

      // Add bot response
      const botMessage = {
        id: messages.length + 2,
        type: 'bot',
        text: data.recommendation,
        risk_score: data.yield_risk_score,
        risk_label: data.yield_risk_label,
        sources: data.sources,
        confidence: data.model_confidence,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      const errorMessage = {
        id: messages.length + 2,
        type: 'error',
        text: `Error: ${error.message}. Make sure the API is running at http://localhost:8001`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const districts = [
    'Thanjavur', 'Tiruvarur', 'Nagapattinam', 'Cuddalore', 
    'Villupuram', 'Kanchipuram', 'Tiruvallur', 'Ranipet'
  ];

  const crops = ['rice', 'sugarcane', 'cotton', 'groundnut', 'maize'];

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 via-white to-amber-50 font-sans">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-gradient-to-r from-emerald-600 to-teal-600 shadow-lg">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-md">
                <span className="text-2xl">🌾</span>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">Krishi Sahaya</h1>
                <p className="text-emerald-100 text-sm">AI Agricultural Advisor</p>
              </div>
            </div>
            <TrendingUp className="w-6 h-6 text-emerald-100" />
          </div>
        </div>
      </div>

      {/* Main Container */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Settings Panel */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6 border-l-4 border-emerald-500">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Your Farm Details</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                📍 District
              </label>
              <select
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                className="w-full px-4 py-2 border-2 border-emerald-200 rounded-lg focus:outline-none focus:border-emerald-500 bg-white text-gray-800"
              >
                {districts.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                🌱 Crop
              </label>
              <select
                value={crop}
                onChange={(e) => setCrop(e.target.value)}
                className="w-full px-4 py-2 border-2 border-emerald-200 rounded-lg focus:outline-none focus:border-emerald-500 bg-white text-gray-800"
              >
                {crops.map(c => (
                  <option key={c} value={c}>
                    {c.charAt(0).toUpperCase() + c.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Chat Container */}
        <div className="bg-white rounded-lg shadow-lg overflow-hidden border border-emerald-100">
          {/* Messages */}
          <div className="h-96 overflow-y-auto p-6 space-y-4 bg-gradient-to-b from-white to-emerald-50">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs lg:max-w-md xl:max-w-lg px-4 py-3 rounded-lg ${
                    msg.type === 'user'
                      ? 'bg-emerald-600 text-white rounded-br-none shadow-md'
                      : msg.type === 'error'
                      ? 'bg-red-100 text-red-800 rounded-bl-none border border-red-300'
                      : 'bg-gray-100 text-gray-800 rounded-bl-none shadow-sm'
                  }`}
                >
                  <p className="text-sm leading-relaxed">{msg.text}</p>

                  {/* Risk Score Badge */}
                  {msg.risk_label && (
                    <div className={`mt-3 pt-3 border-t ${msg.type === 'user' ? 'border-emerald-400' : 'border-gray-300'}`}>
                      <div className="flex items-center gap-2">
                        {msg.risk_label === 'HIGH RISK' ? (
                          <AlertCircle className="w-4 h-4 text-red-500" />
                        ) : (
                          <CheckCircle2 className="w-4 h-4 text-green-500" />
                        )}
                        <span className="text-xs font-semibold">
                          {msg.risk_label}: {(msg.risk_score * 100).toFixed(1)}%
                        </span>
                      </div>
                      {msg.confidence && (
                        <p className="text-xs mt-1 opacity-75">
                          Model confidence: {(msg.confidence * 100).toFixed(0)}%
                        </p>
                      )}
                    </div>
                  )}

                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-300">
                      <p className="text-xs font-semibold mb-1 opacity-75">📚 Sources:</p>
                      <div className="space-y-1">
                        {msg.sources.map((source, i) => (
                          <p key={i} className="text-xs opacity-75 italic">
                            • {source}
                          </p>
                        ))}
                      </div>
                    </div>
                  )}

                  <p className={`text-xs mt-2 ${msg.type === 'user' ? 'text-emerald-100' : 'text-gray-500'}`}>
                    {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 text-gray-800 px-4 py-3 rounded-lg rounded-bl-none flex items-center gap-2 shadow-sm">
                  <Loader className="w-4 h-4 animate-spin text-emerald-600" />
                  <span className="text-sm">Analyzing your farm situation...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <form onSubmit={handleSendMessage} className="border-t border-gray-200 p-4 bg-white">
            <div className="flex gap-3">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Ask about irrigation, pests, government schemes..."
                disabled={loading}
                className="flex-1 px-4 py-3 border-2 border-emerald-200 rounded-lg focus:outline-none focus:border-emerald-500 disabled:opacity-50 text-gray-800 placeholder-gray-400"
              />
              <button
                type="submit"
                disabled={loading || !inputValue.trim()}
                className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white px-6 py-3 rounded-lg font-semibold flex items-center gap-2 transition-colors shadow-md"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              💡 Try: "Should I irrigate during dry weather?" or "What government schemes are available?"
            </p>
          </form>
        </div>

        {/* Footer */}
        <div className="text-center mt-6 text-sm text-gray-600">
          <p>🤖 Powered by: ML Risk Model + RAG System + Rule-based Advisor</p>
          <p className="mt-1">📊 Data from: NASA POWER API + Kaggle + ICAR</p>
          <p className="mt-2 text-xs text-gray-500">⚠️ Always consult local agricultural officers for critical farm decisions</p>
        </div>
      </div>
    </div>
  );
}