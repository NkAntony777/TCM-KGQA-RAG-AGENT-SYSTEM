import '@testing-library/jest-dom'

if (typeof TextDecoder === 'undefined') {
  const { TextDecoder: NodeTextDecoder, TextEncoder: NodeTextEncoder } = require('util')
  global.TextDecoder = NodeTextDecoder
  global.TextEncoder = NodeTextEncoder
}
