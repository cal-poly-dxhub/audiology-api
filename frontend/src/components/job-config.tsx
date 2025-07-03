"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { toast } from "sonner"
import { useState } from "react"

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
  const [isSubmitting, setIsSubmitting] = useState(false)

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
        },
        body: JSON.stringify(jobData),
      })

      if (!response.ok) {
        const errorData = await response.text()
        throw new Error(`HTTP ${response.status}: ${errorData}`)
      }

      const responseData = await response.json()

      // Echo response to console
      console.log("API Response:", JSON.stringify(responseData, null, 2))

      if (responseData.statusCode != 200) {
        toast.error("Job submission failed", {
          description: responseData.body || "An error occurred while submitting the job.",
          action: {
            label: "Retry",
            onClick: () => onSubmit(values),
          },
        })
      } else {
        // Show success toast
        toast.success("Job submitted successfully!", {
          description: `Job "${values.job_name}" has been created`,
          action: {
            label: "View Console",
            onClick: () => console.log("Response data:", responseData),
          },
        })
        form.reset()
      }
    } catch (error) {
      console.error("API Error:", error)

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

  return (
    <div className="max-w-md mx-auto mt-8 p-6 bg-white rounded-lg shadow-md">
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
        </form>
      </Form>
    </div>
  )
}
