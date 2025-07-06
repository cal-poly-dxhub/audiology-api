import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import {
  CognitoIdentityProviderClient,
  InitiateAuthCommand,
  AuthFlowType,
} from "@aws-sdk/client-cognito-identity-provider";

const cognitoClient = new CognitoIdentityProviderClient({
  region: "us-west-2", // Based on your user pool ID
});

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.username || !credentials?.password) {
          return null;
        }

        try {
          const command = new InitiateAuthCommand({
            AuthFlow: AuthFlowType.USER_PASSWORD_AUTH,
            ClientId: process.env.COGNITO_CLIENT_ID!,
            AuthParameters: {
              USERNAME: credentials.username,
              PASSWORD: credentials.password,
            },
          });

          const response = await cognitoClient.send(command);

          if (response.AuthenticationResult?.AccessToken) {
            // You can decode the JWT token to get user info if needed
            return {
              id: credentials.username,
              name: credentials.username,
              email: credentials.username, // Assuming username is email
              accessToken: response.AuthenticationResult.AccessToken,
              refreshToken: response.AuthenticationResult.RefreshToken,
              idToken: response.AuthenticationResult.IdToken,
            };
          }

          return null;
        } catch (error) {
          console.error("Cognito authentication error:", error);
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.refreshToken = user.refreshToken;
        token.idToken = user.idToken;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.refreshToken = token.refreshToken as string;
      session.idToken = token.idToken as string;
      return session;
    },
  },
  pages: {
    signIn: "/auth/signin",
  },
  session: {
    strategy: "jwt",
  },
  secret: process.env.NEXTAUTH_SECRET,
});

export { handler as GET, handler as POST };
