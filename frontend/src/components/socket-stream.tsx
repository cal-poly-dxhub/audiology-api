"use client"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"

interface SocketStreamProps {
  isFileUploaded: boolean
  jobId?: string
}

interface StreamMessage {
  id: string
  timestamp: string
  type: 'info' | 'error' | 'success' | 'warning'
  message: string
}

export function SocketStream({ isFileUploaded, jobId }: SocketStreamProps) {
  const [isConnected, setIsConnected] = useState(false)
  const [messages, setMessages] = useState<StreamMessage[]>([])
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isFileUploaded) {
      // Disconnect if file is not uploaded
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setIsConnected(false)
      setConnectionStatus('disconnected')
      setMessages([])
      return
    }

    // Wait 1 second after file upload before connecting to WebSocket
    const connectionTimer = setTimeout(() => {
      // Connect to WebSocket when file is uploaded
      const connectWebSocket = () => {
        const wsUrl = process.env.NEXT_PUBLIC_WS_ENDPOINT
        if (!wsUrl) {
          console.error('WebSocket endpoint not configured')
          setConnectionStatus('error')
          return
        }

        setConnectionStatus('connecting')

        try {
          if (jobId) {
            // For WebSocket connections, we need to pass headers via subprotocols or query params
            // Since WebSocket headers are limited, we'll use query parameters
            const wsUrlWithJobName = `${wsUrl}?jobId=${encodeURIComponent(jobId)}`
            wsRef.current = new WebSocket(wsUrlWithJobName)
          } else {
            wsRef.current = new WebSocket(wsUrl)
          }

          wsRef.current.onopen = () => {
            setIsConnected(true)
            setConnectionStatus('connected')
            addMessage('info', `Connected to processing stream. Monitoring job ${jobId}.`)
          }

          wsRef.current.onmessage = (event) => {
            try {
              let parsedData = JSON.parse(event.data)
              let messageType: StreamMessage['type'] = 'info'

              if ("error" in parsedData) {
                messageType = 'error'
                parsedData = parsedData.error
              } else if ("output" in parsedData) {
                messageType = 'success'
                parsedData = parsedData.output
              }

              const formattedData = JSON.stringify(parsedData, null, 2)
              addMessage(messageType, formattedData)
            } catch (error) {
              if (error instanceof SyntaxError) {
                addMessage('info', event.data)
              } else {
                console.error("Error occurred when receiving WebSocket message:", error)
                addMessage('error', 'Unexpected error while decoding server message.')
              }
            }
          }

          wsRef.current.onclose = () => {
            setIsConnected(false)
            setConnectionStatus('disconnected')
            addMessage('warning', 'Connection closed')
          }

          wsRef.current.onerror = (error) => {
            setConnectionStatus('error')
            addMessage('error', 'WebSocket connection error')
            console.error('WebSocket error:', error)
          }
        } catch (error) {
          setConnectionStatus('error')
          addMessage('error', 'Failed to establish WebSocket connection')
          console.error('WebSocket connection failed:', error)
        }
      }

      connectWebSocket()
    }, 1000) // 1 second delay

    // Cleanup on unmount or dependency change
    return () => {
      clearTimeout(connectionTimer)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [isFileUploaded, jobId])

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]')
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight
      }
    }
  }, [messages])

  const addMessage = (type: StreamMessage['type'], message: string) => {
    const newMessage: StreamMessage = {
      id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
      timestamp: new Date().toLocaleTimeString(),
      type,
      message
    }
    setMessages(prev => [...prev, newMessage])
  }

  const getStatusBadgeVariant = () => {
    switch (connectionStatus) {
      case 'connected': return 'default'
      case 'connecting': return 'secondary'
      case 'error': return 'destructive'
      default: return 'outline'
    }
  }

  const getStatusText = () => {
    switch (connectionStatus) {
      case 'connected': return 'Connected'
      case 'connecting': return 'Connecting...'
      case 'error': return 'Error'
      default: return 'Disconnected'
    }
  }

  const getMessageTypeColor = (type: StreamMessage['type']) => {
    switch (type) {
      case 'error': return 'text-red-600'
      case 'success': return 'text-green-600'
      case 'warning': return 'text-yellow-600'
      default: return 'text-gray-700'
    }
  }

  return (
    <Card className={`h-full ${!isFileUploaded ? 'opacity-50 pointer-events-none' : ''}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Processing Stream</CardTitle>
          <Badge variant={getStatusBadgeVariant()}>
            {getStatusText()}
          </Badge>
        </div>
        {jobId && (
          <p className="text-sm text-gray-600">Monitoring: {jobId}</p>
        )}
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-128 px-4 pb-4" ref={scrollAreaRef}>
          {!isFileUploaded ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              <p className="text-center">
                Upload a file to start processing stream<br />
                <span className="text-sm">Real-time updates will appear here</span>
              </p>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              <p className="text-center">
                Waiting for processing updates...<br />
                <span className="text-sm">Messages will appear as they arrive</span>
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {messages.map((msg) => (
                <div key={msg.id} className="text-sm border-l-2 border-gray-200 pl-3 py-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-gray-500">{msg.timestamp}</span>
                    <Badge variant="outline" className="text-xs">
                      {msg.type}
                    </Badge>
                  </div>
                  <p className={`${getMessageTypeColor(msg.type)} whitespace-pre-wrap font-mono text-sm`}>{msg.message}</p>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
