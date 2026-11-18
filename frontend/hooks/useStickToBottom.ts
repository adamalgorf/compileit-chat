"use client"

import { useCallback, useEffect, useRef, useState } from "react"

/** How close to the bottom (px) counts as "at the bottom" again. */
const THRESHOLD = 80

/**
 * Keep a scroll container pinned to the bottom while content grows (streamed tokens), stop
 * following as soon as the user scrolls up, and resume when they get back to the bottom.
 *
 * Only an upward scroll disengages following. Content growth (e.g. source cards appearing
 * at once) and the browser's scroll anchoring can leave the view far from the bottom without
 * any user action, so "distance from bottom" alone is not a reliable signal of intent.
 */
export function useStickToBottom<
  Scroll extends HTMLElement = HTMLDivElement,
  Content extends HTMLElement = HTMLDivElement,
>() {
  const scrollRef = useRef<Scroll>(null)
  const contentRef = useRef<Content>(null)
  const followingRef = useRef(true)
  const [following, setFollowingState] = useState(true)

  const setFollowing = useCallback((value: boolean) => {
    followingRef.current = value
    setFollowingState(value)
  }, [])

  const scrollToBottom = useCallback(
    (behavior: ScrollBehavior = "smooth") => {
      const element = scrollRef.current
      if (!element) return
      setFollowing(true)
      element.scrollTo({ top: element.scrollHeight, behavior })
    },
    [setFollowing],
  )

  useEffect(() => {
    const element = scrollRef.current
    if (!element) return
    let lastTop = element.scrollTop
    const onScroll = () => {
      const top = element.scrollTop
      const distance = element.scrollHeight - top - element.clientHeight
      if (distance < THRESHOLD) setFollowing(true)
      else if (top < lastTop - 1) setFollowing(false) // the user scrolled up
      lastTop = top
    }
    element.addEventListener("scroll", onScroll, { passive: true })
    return () => element.removeEventListener("scroll", onScroll)
  }, [setFollowing])

  useEffect(() => {
    const scroll = scrollRef.current
    const content = contentRef.current
    if (!scroll || !content) return
    const observer = new ResizeObserver(() => {
      if (followingRef.current) scroll.scrollTo({ top: scroll.scrollHeight })
    })
    observer.observe(content)
    return () => observer.disconnect()
  }, [])

  return { scrollRef, contentRef, atBottom: following, scrollToBottom }
}
