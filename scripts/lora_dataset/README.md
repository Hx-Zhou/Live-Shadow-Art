# LoRA 数据准备工具

这些脚本只从提供逐文件许可证元数据的官方开放接口下载候选图。下载结果仍须人工复核；“通过许可证过滤”不等于“已经适合训练”。

当前来源：

- Wikimedia Commons：Public Domain、CC0、CC BY、CC BY-SA、CC BY-NC、CC BY-NC-SA；自动排除所有 ND 许可证。
- The Metropolitan Museum of Art Open Access：只保留 API 标记 `isPublicDomain=true` 的对象。

每张图保留来源页、作者、许可证、许可链接、原图链接和 SHA256。训练前必须完成视觉质量、地域风格、近重复和训练/验证泄漏检查。

本数据集服务于非商业课程展示。带 NC 条款的记录会标记 `noncommercial_only=true`；由这些数据训练的 adapter 不得未经重新授权用于商业目的。
