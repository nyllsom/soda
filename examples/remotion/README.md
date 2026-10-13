# Remotion 教学：图标与图表动画

此例生成浏览器 HTML 演示稿，不是 PowerPoint `.pptx` 文件。已全局安装新版 SODA 后，无需给讲稿单独安装 React 或 Remotion：

```bash
soda example remotion --copy my-remotion-talk
cd my-remotion-talk
soda preview deck.md
# 或生成可离线分享的单文件
soda deck.md -o talk.html
```

也可运行 `soda example remotion` 查看内置预览。空格播放到下一讲解步骤，左箭头回退，底部进度条可任意跳转。

## 1. Markdown 引用组件

```markdown
@remotion icon.tsx {#check}
@embed chart.tsx {#bars progress=0}
```

支持本地 `.js`、`.mjs`、`.jsx`、`.ts`、`.tsx` 文件；`@embed` 根据这些扩展名推断 Remotion，展示代码请明确写 `type=code`。旧的 `@zanim` 和 `type=zanim` 已移除，不能只改指令名继续使用旧的 mount 模块。

## 2. React 描述画面

`icon.tsx` 默认导出 React 组件，并导出：

```tsx
export const config = {width: 960, height: 540, fps: 30, durationInFrames: 180};
export const defaultProps = {label: '准备就绪', color: '#6f145f'};
```

不导出 config 时默认 960 × 540、30 fps、300 帧。`fit=contain` 保持比例居中；`fit=cover` 裁切填满，`fit=fill` 拉伸填满。这里是组件本身，不是 `registerRoot()` 入口，也不是 `<Composition>`。组件可直接复用到自己的 Remotion Studio 项目。

图标使用 `useCurrentFrame()` 取得帧号，`spring()` 计算弹性缩放，`interpolate()` 计算勾线进度。SODA 用 **本页经过的秒数 × fps** 求帧号，向下取整，并限制在 0 到 durationInFrames − 1。时间轴暂停时画面也暂停，不独立自动播放、不循环。

```soda
motion icon {
    step "图标入场" { wait 1600ms; }
}
```

`wait` 为帧动画预留播放时间；组件的 durationInFrames 不会自动延长讲稿时间轴。不写 `.soda` 时生成静态初始帧。

## 3. SODA 驱动组件参数

`chart.tsx` 接收 progress，把初始柱高线性转换成增长后的柱高：

```soda
motion chart {
    step "增长" {
        bars.set(name = "label", value = "增长后");
        bars.animate(name = "progress", from = 0, to = 1,
                     duration = 1800ms, easing = LINEAR);
    }
}
```

`defaultProps` 提供组件初值，Markdown 属性覆盖它，随后 `.set()` / `.animate()` 的结果覆盖同名属性。Markdown 中的属性值可能是字符串，数值参数建议像例子一样用 `Number(progress)` 归一化，并为 `.animate()` 明确写 `from`。不要用 setInterval、Date.now 或随机数推动画面，否则回退与跳转不能复现相同结果。

## 4. 打包与迁移

React、Remotion Player、组件和相对 import 的代码由 esbuild 打包进 HTML；普通导出和单文件导出都不需要运行时 CDN。png/jpg/svg import 会内嵌；推荐用本例的内联 SVG 图标。其他依赖请在讲稿项目本地安装。网络 URL、`staticFile()` 的 public 目录、独立 CSS 文件、字体和音视频不会自动收集，需自行安排资源；离线教学例不依赖这些资源。

从 Zanim 迁移时，把 `mount/render/destroy` 改为默认导出的 React 组件，把 `render(time, props)` 中的计算改为 `useCurrentFrame()` 与组件 props。原 `.soda` 的 set/animate、通用入场和退场动作可继续使用。

直接使用 Python 包时，还需 npm 安装 react、react-dom、remotion、@remotion/player、esbuild，并用 `SODA_NODE_MODULES` 指向该 node_modules。remotion 与 @remotion/player 版本必须一致。

官方参考：[Player](https://www.remotion.dev/docs/player)、[useCurrentFrame](https://www.remotion.dev/docs/use-current-frame)、[spring](https://www.remotion.dev/docs/spring)。Remotion 的许可适用于其依赖，参见 [Remotion License](https://www.remotion.dev/license)。
