package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 下载中心导出记录：仅创建人可见可操作。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("biz_download_record")
public class DownloadRecord extends BaseEntity {

    /** task / market_project */
    private String objectType;
    private String filename;
    private String filePath;
}
