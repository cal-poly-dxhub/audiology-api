import { JobConfigForm } from "@/components/job-config"

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="container mx-auto px-4">
        <h1 className="text-4xl font-bold text-center mb-4">Welcome to My Page</h1>
        <p className="text-center text-gray-600 mb-8">This is a simple page built with Next.js.</p>
        <JobConfigForm />
      </div>
    </div>
  );
}
