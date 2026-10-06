# Source separation note

The supplied ARM AI Image Enhancer 2.2.8 archive was reviewed to understand the user's workflow and the requested feature set. Its root archive did not contain an explicit license granting reuse of the project's own application source code.

To keep this private build technically separate from the upstream owner, SignPrint AI Enhancer was implemented in a new directory with new source files and new branding. It does **not** copy the upstream GUI source, installer source, logo, QR image, donation links, or application assets, and it does not perform any Git operation against the upstream repository.

The independent build can optionally download the official third-party Real-ESRGAN NCNN/Vulkan release directly from the Real-ESRGAN upstream project. Those third-party components remain subject to their own licenses and model terms.
