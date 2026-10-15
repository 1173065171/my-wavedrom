# my-wavedrom 开发约定

本仓库 fork 自 [wavedrom/wavedrom](https://github.com/wavedrom/wavedrom)，在其上做自有版本的迭代。

## 分支

- `trunk`：上游 `wavedrom/wavedrom` 的镜像，只做快进同步，不提交自己的改动。
- `my-dev`：自有版本的主线，自己的迭代都在这里集成。
- `claude/*`：Claude 的开发分支。从 `my-dev` 拉出，完成后用 `git merge --no-ff` 合并回 `my-dev`。

## 同步上游

```bash
git remote add upstream https://github.com/wavedrom/wavedrom.git   # 新克隆时添加一次
git fetch upstream trunk
git push origin upstream/trunk:trunk      # 只能快进；被拒说明 trunk 混进了自己的提交
git checkout my-dev && git merge trunk    # 解决冲突、跑测试后推送 my-dev
```

进行中的 `claude/*` 分支随后从 `my-dev` 合并更新。也可以在 GitHub 上把分支切到 `trunk` 后点 Sync fork，代替前三步。

## 减少与上游的冲突

- 新功能尽量放在新文件里，对上游已有文件只做最小的接入改动。
- `.github/workflows/ci.yml` 与上游保持一致；自己的 CI 放在独立的 workflow 文件里（如 `fsdb2wave.yml`）。
- 不改 `package.json` 的 `version`，上游每次发版都会改它。

## 测试

```bash
npm i && npm test                                         # eslint + mocha
python3 -m unittest discover -s tools/fsdb2wave/tests     # fsdb2wave（Python ≥ 3.8）
npm run view                                              # 构建 <wave-view> bundle，演示页 test/test-theme.html
```

设计文档在 `docs/design/`。
