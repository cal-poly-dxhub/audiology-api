"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { toast } from "sonner"
import { useState, useRef } from "react"
import { useSession, signOut } from "next-auth/react"

import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { SocketStream } from "@/components/socket-stream"

const formSchema = z.object({
  job_name: z.string().min(1, {
    message: "Job name is required.",
  }),
  config_id: z.string().min(1, {
    message: "Config ID is required.",
  }),
  institution_id: z.string().min(1, {
    message: "Institution ID is required.",
  }),
  mime_type: z.string().min(1, {
    message: "MIME type is required.",
  }),
})

export function JobConfigForm() {
  const { data: session, status } = useSession()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadUrl, setUploadUrl] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isFileUploaded, setIsFileUploaded] = useState(false)
  const [submittedJobId, setSubmittedJobId] = useState<string>("")
  const fileInputRef = useRef<HTMLInputElement>(null)

  if (!session && status !== "loading") {
    signOut({ callbackUrl: '/auth/signin' })
  }

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      job_name: "",
      config_id: "",
      institution_id: "",
      mime_type: "",
    },
  })

  async function onSubmit(values: z.infer<typeof formSchema>) {
    setIsSubmitting(true)

    // Format the data to match the API structure
    const jobData = {
      job_name: values.job_name,
      config_id: values.config_id,
      institution_id: values.institution_id,
      mime_type: values.mime_type
    }

    try {
      const endpoint = process.env.NEXT_PUBLIC_JOB_ENDPOINT
      console.log("Submitting job data:", JSON.stringify(jobData, null, 2))
      console.log("Using endpoint:", endpoint)

      if (!endpoint) {
        throw new Error("JOB_ENDPOINT environment variable is not configured")
      }

      const response = await fetch(`${endpoint}/upload`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session?.accessToken || ''}`,
          "X-API-Key": "placeholder" // Superseded by Authorization header
        },
        body: JSON.stringify(jobData),
      })

      if (!response.ok) {
        const errorData = await response.text()
        throw new Error(`HTTP ${response.status}: ${errorData}`)
      }

      const responseData = await response.json()
      const jobId = responseData.body?.job_id

      if (!jobId) {
        throw new Error("Job ID not found in response")
      }

      // Echo response to console
      console.log("API Response:", JSON.stringify(responseData, null, 2))

      if (responseData.statusCode != 200) {
        // Extract error reason from response body
        const errorReason = typeof responseData.body === 'string'
          ? responseData.body
          : responseData.body?.message || responseData.body || "An error occurred while submitting the job."

        toast.error("Job submission failed", {
          description: errorReason,
          action: {
            label: "Retry",
            onClick: () => onSubmit(values),
          },
        })
      } else {
        // Extract upload URL from successful response
        const uploadUrlFromResponse = responseData.body?.url

        if (uploadUrlFromResponse) {
          setUploadUrl(uploadUrlFromResponse)
        }

        // Store job id for later use
        setSubmittedJobId(jobId)

        // Show success toast
        toast.success("Job submitted successfully!", {
          description: `Job "${values.job_name}" has been created. You can now upload a file.`,
        })
        // Don't reset form so user can see the upload button
      }
    } catch (error) {
      console.error("API Error:", error)

      // If this is a 401 or a 403, simply ask the user to sign out.
      if (error instanceof Error && (error.message.includes("401") || error.message.includes("403"))) {
        toast.error("Session expired. Please sign in again.", {
          action: {
            label: "Sign In",
            onClick: () => signOut({ callbackUrl: '/auth/signin' }),
          },
        })
        return
      }

      // Show error toast
      toast.error("Failed to submit job", {
        description: error instanceof Error ? error.message : "An unexpected error occurred",
        action: {
          label: "Retry",
          onClick: () => onSubmit(values),
        },
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleFileUpload() {
    if (!uploadUrl || !fileInputRef.current?.files?.[0]) {
      toast.error("No file selected", {
        description: "Please select a file to upload.",
      })
      return
    }

    const file = fileInputRef.current.files[0]
    setIsUploading(true)

    try {
      const response = await fetch(uploadUrl, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': file.type,
        },
      })

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status} ${response.statusText}`)
      }

      toast.success("File uploaded successfully!", {
        description: `${file.name} has been uploaded to S3.`,
      })

      // Set file as uploaded to start WebSocket connection
      setIsFileUploaded(true)

      // Reset upload URL but keep job name for WebSocket
      setUploadUrl(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      // Don't reset form or job name yet - let user see the stream

    } catch (error) {
      console.error("Upload Error:", error)
      toast.error("File upload failed", {
        description: error instanceof Error ? error.message : "An unexpected error occurred during upload",
        action: {
          label: "Retry",
          onClick: () => handleFileUpload(),
        },
      })
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto mt-8 p-6">
      {/* Sign-out section */}
      {session && (
        <div className="mb-6 flex justify-end">
          <div className="bg-white rounded-lg shadow-sm p-4 flex items-center gap-4">
            <span className="text-sm text-gray-600">
              Signed in as <span className="font-medium">{session.user?.email}</span>
            </span>
            <Button
              onClick={() => signOut({ callbackUrl: '/auth/signin' })}
              variant="outline"
              size="sm"
              className="text-red-600 border-red-200 hover:bg-red-50 hover:border-red-300"
            >
              Sign Out
            </Button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Main Form */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-2xl font-bold mb-6 text-center">Job Configuration</h2>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <FormField
                control={form.control}
                name="job_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Job Name</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., report_sample" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="config_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Config ID</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., NotTestConfig" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="institution_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Institution ID</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Redcap" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="mime_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>MIME Type</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., text/csv" {...field} />
                    </FormControl>
                    <FormDescription>
                      Specify the file format type.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Submitting..." : "Submit Job"}
              </Button>

              {/* File Upload Section */}
              <div className="mt-4 space-y-4">
                <div>
                  <label htmlFor="file-upload" className="block text-sm font-medium text-gray-700 mb-2">
                    Select file to upload
                  </label>
                  <input
                    id="file-upload"
                    ref={fileInputRef}
                    type="file"
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                    disabled={!uploadUrl}
                  />
                </div>
                <Button
                  type="button"
                  onClick={handleFileUpload}
                  className="w-full"
                  disabled={!uploadUrl || isUploading}
                  variant={uploadUrl ? "default" : "secondary"}
                >
                  {isUploading ? "Uploading..." : uploadUrl ? "Upload File" : "Upload File (Submit job first)"}
                </Button>
              </div>
            </form>
          </Form>
        </div>

        {/* Socket Stream */}
        <div>
          <SocketStream
            isFileUploaded={isFileUploaded}
            jobId={submittedJobId}
          />
        </div>
      </div>
    </div>
  )
}
