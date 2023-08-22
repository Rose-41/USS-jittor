import jittor as jt
from jittor import nn
from src.bricks import ConvModule

from src.ops import resize
from src.utils_van.registry import HEADS
from .decode_head import BaseDecodeHead


class PPM(nn.ModuleList):

    def __init__(self, pool_scales, in_channels, channels, conv_cfg, norm_cfg,
                 act_cfg, align_corners, **kwargs):
        super(PPM, self).__init__()
        self.pool_scales = pool_scales
        self.align_corners = align_corners
        self.in_channels = in_channels
        self.channels = channels
        self.conv_cfg = conv_cfg
        self.norm_cfg = norm_cfg
        self.act_cfg = act_cfg
        for pool_scale in pool_scales:
            self.append(
                nn.Sequential(
                    nn.AdaptiveAvgPool2d(pool_scale),
                    ConvModule(self.in_channels,
                               self.channels,
                               1,
                               conv_cfg=self.conv_cfg,
                               norm_cfg=self.norm_cfg,
                               act_cfg=self.act_cfg,
                               **kwargs)))

    def execute(self, x):
        ppm_outs = []
        for ppm in self:
            ppm_out = ppm(x)
            upsampled_ppm_out = resize(ppm_out,
                                       size=x.size()[2:],
                                       mode='bilinear',
                                       align_corners=self.align_corners)
            ppm_outs.append(upsampled_ppm_out)
        return ppm_outs


@HEADS.register_module()
class PSPHead(BaseDecodeHead):

    def __init__(self, pool_scales=(1, 2, 3, 6), **kwargs):
        super(PSPHead, self).__init__(**kwargs)
        assert isinstance(pool_scales, (list, tuple))
        self.pool_scales = pool_scales
        self.psp_modules = PPM(self.pool_scales,
                               self.in_channels,
                               self.channels,
                               conv_cfg=self.conv_cfg,
                               norm_cfg=self.norm_cfg,
                               act_cfg=self.act_cfg,
                               align_corners=self.align_corners)
        self.bottleneck = ConvModule(self.in_channels +
                                     len(pool_scales) * self.channels,
                                     self.channels,
                                     3,
                                     padding=1,
                                     conv_cfg=self.conv_cfg,
                                     norm_cfg=self.norm_cfg,
                                     act_cfg=self.act_cfg)

    def execute(self, inputs):
        x = self._transform_inputs(inputs)
        psp_outs = [x]
        psp_outs.extend(self.psp_modules(x))
        psp_outs = jt.concat(psp_outs, dim=1)
        output = self.bottleneck(psp_outs)
        output = self.cls_seg(output)
        return output
