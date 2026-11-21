import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthProvider'
import ChatbotWidget from './ChatbotWidget'

describe('ChatbotWidget', () => {
	it('renderiza negrito Markdown como texto em destaque', async () => {
		Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
			configurable: true,
			value: vi.fn(),
		})
		render(
			<AuthProvider>
				<ChatbotWidget />
			</AuthProvider>,
		)

		fireEvent.click(screen.getByRole('button', { name: 'Abrir assistente virtual' }))

		expect(await screen.findByText('Organiza AI', { selector: 'strong' })).toBeInTheDocument()
	})
})