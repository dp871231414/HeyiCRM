package com.heyi.server.config;

import cn.dev33.satoken.stp.StpUtil;
import com.baomidou.mybatisplus.annotation.DbType;
import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.plugins.inner.PaginationInnerInterceptor;
import org.apache.ibatis.reflection.MetaObject;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.LocalDateTime;

@Configuration
public class MybatisPlusConfig {

    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        interceptor.addInnerInterceptor(new PaginationInnerInterceptor(DbType.MYSQL));
        return interceptor;
    }

    /**
     * createdAt / updatedAt / createdBy / updatedBy 由此处统一填充。
     * 说明：@DynamicUserFields 切面只能处理入参为 BaseEntity 的方法，而各 Biz 接收的是 Form，
     * 因此审计人统一放在 MP 填充器里，保证任何入口的 insert/update 都能写入。
     */
    @Bean
    public MetaObjectHandler metaObjectHandler() {
        return new MetaObjectHandler() {
            @Override
            public void insertFill(MetaObject metaObject) {
                LocalDateTime now = LocalDateTime.now();
                this.strictInsertFill(metaObject, "createdAt", LocalDateTime.class, now);
                this.strictInsertFill(metaObject, "updatedAt", LocalDateTime.class, now);
                String account = currentAccount();
                if (account != null) {
                    this.strictInsertFill(metaObject, "createdBy", String.class, account);
                    this.strictInsertFill(metaObject, "updatedBy", String.class, account);
                }
                Object deletedAt = metaObject.getValue("deletedAt");
                if (deletedAt == null) {
                    this.strictInsertFill(metaObject, "deletedAt", Long.class, 0L);
                }
            }

            @Override
            public void updateFill(MetaObject metaObject) {
                this.strictUpdateFill(metaObject, "updatedAt", LocalDateTime.class, LocalDateTime.now());
                String account = currentAccount();
                if (account != null) {
                    this.strictUpdateFill(metaObject, "updatedBy", String.class, account);
                }
            }

            /** 当前登录账号；未登录返回 null。 */
            private String currentAccount() {
                try {
                    if (!StpUtil.isLogin()) {
                        return null;
                    }
                    Object loginId = StpUtil.getLoginId();
                    return loginId == null ? null : String.valueOf(loginId);
                } catch (Exception e) {
                    return null;
                }
            }
        };
    }
}
