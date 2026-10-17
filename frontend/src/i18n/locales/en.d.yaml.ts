import type { Messages } from './ru.yaml'

declare const messages: {
  [Namespace in keyof Messages]?: Partial<Messages[Namespace]>
}
export default messages
