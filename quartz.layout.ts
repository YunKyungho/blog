import { PageLayout, SharedLayout } from "./quartz/cfg"
import * as Component from "./quartz/components"

/**
 * 개발 블로그 최적화 레이아웃
 * - 코드 중심 콘텐츠에 최적화
 * - 깔끔한 네비게이션
 * - 검색 및 태그 기능 강조
 */

// 모든 페이지 공통 컴포넌트
export const sharedPageComponents: SharedLayout = {
  head: Component.Head(),
  header: [Component.Spacer()],  // 빈 배열 대신 Spacer 추가
  afterBody: [],  // 이것도 명시적으로 추가
  footer: Component.Footer({
    links: {
      GitHub: "https://github.com/YunKyungho",
      Email: "mailto:sghj2020s@gmail.com",
    },
  }),
}

// 데스크탑 왼쪽 사이드바
export const defaultContentPageLayout: PageLayout = {
  beforeBody: [
    Component.Breadcrumbs(),
    Component.ArticleTitle(),
    Component.ContentMeta(),
    Component.TagList(),
  ],
  afterBody: [
    Component.Comments({
      provider: 'giscus',
      options: {
        repo: 'YunKyungho/blog',
        repoId: 'R_kgDORCb2IA',
        category: 'Announcements',
        categoryId: 'DIC_kwDORCb2IM4C1fsk',
      }
    }),
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Search(),
    Component.Darkmode(),
    Component.DesktopOnly(
      Component.Explorer({
        title: "📁 Contents",
        folderClickBehavior: "collapse",
        folderDefaultState: "collapsed",
        useSavedState: true,
        sortFn: (a, b) => {
          // 폴더 우선, 이름순 정렬
          if ((!a.file && !b.file) || (a.file && b.file)) {
            return a.displayName.localeCompare(b.displayName, "ko")
          }
          if (a.file && !b.file) {
            return 1
          } else {
            return -1
          }
        },
      })
    ),
  ],
  right: [
    Component.Graph({
      localGraph: {
        drag: true,
        zoom: true,
        depth: 1,
        scale: 1.1,
        repelForce: 0.5,
        centerForce: 0.3,
        linkDistance: 30,
        fontSize: 0.6,
        opacityScale: 1,
        removeTags: [],
        showTags: true,
      },
      globalGraph: {
        drag: true,
        zoom: true,
        depth: -1,
        scale: 0.9,
        repelForce: 0.5,
        centerForce: 0.3,
        linkDistance: 30,
        fontSize: 0.6,
        opacityScale: 1,
        removeTags: [],
        showTags: true,
      },
    }),
    Component.DesktopOnly(Component.TableOfContents()),
    Component.Backlinks(),
  ],
}

// 리스트 페이지 (태그, 폴더 페이지)
export const defaultListPageLayout: PageLayout = {
  beforeBody: [Component.Breadcrumbs(), Component.ArticleTitle(), Component.ContentMeta()],
  afterBody: [
    Component.Comments({
      provider: 'giscus',
      options: {
        repo: 'YunKyungho/blog',
        repoId: 'R_kgDORCb2IA',
        category: 'Announcements',
        categoryId: 'DIC_kwDORCb2IM4C1fsk',
      }
    }),    
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Search(),
    Component.Darkmode(),
    Component.DesktopOnly(Component.Explorer()),
  ],
  right: [],
}

// 404 페이지
export const default404PageLayout: PageLayout = {
  beforeBody: [Component.ArticleTitle()],
  afterBody: [],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Search(),
    Component.Darkmode(),
  ],
  right: [],
}

export default {
  sharedPageComponents,
  defaultContentPageLayout,
  defaultListPageLayout,
  default404PageLayout,
}