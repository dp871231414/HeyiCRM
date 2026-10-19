package com.heyi.publics.common.base;

import com.baomidou.mybatisplus.extension.service.IService;

/**
 * Service 顶层接口：继承 MP 的 IService，业务 Service 不再重复声明内置 CRUD。
 */
public interface SuperService<P> extends IService<P> {
}
