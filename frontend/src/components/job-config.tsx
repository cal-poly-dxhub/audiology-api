"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"

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
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      job_name: "",
      config_id: "",
      institution_id: "",
      mime_type: "",
    },
  })

  function onSubmit(values: z.infer<typeof formSchema>) {
    // Format the data to match the API structure
    const jobData = {
      job_name: values.job_name,
      config_id: values.config_id,
      institution_id: values.institution_id,
      mime_type: values.mime_type
    }

    console.log("Job Configuration:", JSON.stringify(jobData, null, 2))
    alert("Job configuration submitted! Check the console for JSON output.")

    // Here you would typically send the data to your API endpoint
    // Example: POST request with jobData
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
          <Button type="submit" className="w-full">
            Submit Job
          </Button>
        </form>
      </Form>
    </div>
  )
}
