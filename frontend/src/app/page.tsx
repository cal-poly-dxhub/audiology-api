import { JobConfigForm } from "@/components/job-config"

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="container mx-auto px-4">
        <JobConfigForm />
      </div>
    </div>
  );
}
