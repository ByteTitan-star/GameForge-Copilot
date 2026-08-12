import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { ThemeBootstrap } from '@/components/theme/ThemeBootstrap'
import { Toaster } from '@/components/ui/Toaster'
import { AppRoutes } from '@/routes'
import { queryClient } from '@/lib/query-client'

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeBootstrap />
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
      <Toaster />
    </QueryClientProvider>
  )
}
