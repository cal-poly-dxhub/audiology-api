"use client"

import { useSession, signIn, signOut } from "next-auth/react"

export default function AuthExample() {
  const { data: session, status } = useSession()

  if (status === "loading") return <p>Loading...</p>

  if (session) {
    return (
      <div className="p-4 border rounded-lg">
        <p className="mb-2">Signed in as {session.user?.email}</p>
        <p className="mb-2 text-sm text-gray-600">
          Access Token: {session.accessToken ? "Available" : "Not available"}
        </p>
        <button
          onClick={() => signOut()}
          className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
        >
          Sign out
        </button>
      </div>
    )
  }

  return (
    <div className="p-4 border rounded-lg">
      <p className="mb-2">Not signed in</p>
      <button
        onClick={() => signIn()}
        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
      >
        Sign in
      </button>
    </div>
  )
}
